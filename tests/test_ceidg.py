"""ceidg.py (Łowca, CEIDG API v3): stronicowanie, format leada, minimum danych osobowych, token, ponowienia; bez sieci."""

from __future__ import annotations

import base64
import csv
import datetime as dt
import json
import os
import sys
import urllib.parse
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profiles" / "jarvo-lowca" / "scripts"))
import ceidg  # noqa: E402
import leady  # noqa: E402
import lowca_lib as ll  # noqa: E402

API = ceidg.API["produkcja"]
ID1, ID2, ID3 = ("9D2531B1-6DED-4538-95EA-22FF2C7D2E20", "6976CDA9-521A-44BE-9216-8EB1B459A68F",
                 "31F87519-9395-4FCF-8E19-6D5C0522FA7A")
# dane, które nie mogą wyjść ze skryptu (przedsiębiorca to osoba fizyczna)
PRYWATNE = ("Janina", "Testowa", "ul. Domowa", "Prywatna", "85010112345", "AE:PL-12345-67890", "Ukraina", "zakaz prowadzenia",
            "Syndyk", "Zarządca", "dyplom", "signal: 600 700 800")


def _jwt(exp: int) -> str:
    """Token w kształcie JWT (do testów, niczego nie otwiera)."""
    czesc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")  # noqa: E731
    return f"{czesc({'alg': 'none'})}.{czesc({'exp': exp, 'sub': 'test'})}.podpis-testowy-ceidg"


TOKEN = _jwt(int(dt.datetime(2027, 1, 1, tzinfo=dt.timezone.utc).timestamp()))


def _adres(miasto="Gliwice"):
    return {"ulica": "ul. Prywatna", "budynek": "7", "lokal": "3", "miasto": miasto, "wojewodztwo": "ŚLĄSKIE",
            "powiat": "Gliwice", "gmina": "Gliwice", "kraj": "PL", "kod": "44-100", "terc": "2466011", "simc": "0940139"}


def _lista_wpis(id_, nazwa, start):
    return {"id": id_, "nazwa": nazwa, "adresDzialalnosci": _adres(),
            "wlasciciel": {"imie": "Janina", "nazwisko": "Testowa", "nip": "6312345678", "regon": "123456785"},
            "dataRozpoczecia": start, "status": "AKTYWNY", "link": f"{API}/firma/{id_}"}


def _pelny(id_, nazwa, start, kod="4331Z", inne="4334Z", email=None, telefon=None, www=None, nip="5250000251"):
    f = _lista_wpis(id_, nazwa, start)
    f["wlasciciel"] = {"imie": "Janina", "nazwisko": "Testowa", "nip": nip, "regon": "123456785", "pesel": "85010112345"}
    f.update({"adresKorespondencyjny": {"ulica": "ul. Domowa", "budynek": "1", "miasto": "Zabrze"},
              "adresyDzialalnosciDodatkowe": [{"ulica": "ul. Domowa", "miasto": "Bytom"}],
              "obywatelstwa": [{"symbol": "UA", "kraj": "Ukraina"}], "rokPkd": "2007",
              "pkd": [{"kod": kod, "nazwa": "Tynkowanie"}, {"kod": inne, "nazwa": "Inne roboty"}],
              "pkdGlowny": {"kod": kod, "nazwa": "Tynkowanie"}, "telefon": telefon, "email": email, "www": www,
              "adresDoreczenElektronicznych": "AE:PL-12345-67890", "innaFormaKonaktu": "signal: 600 700 800",
              "wspolnoscMajatkowa": 1, "dataZgonu": None, "pesel": "85010112345",
              "zakazy": [{"typ": "zakaz prowadzenia", "opis": "zakaz prowadzenia działalności"}],
              "upadlosci": [{"rodzajInformacji": "upadłość", "imie": "Syndyk", "nazwisko": "Syndyk"}],
              "zarzadcaSukcesyjny": {"imie": "Zarządca", "nazwisko": "Zarządca", "telefon": "600 700 801"},
              "kwalifikacjeZawodowe": [{"zawod": "tynkarz", "wydanyPrzez": "dyplom"}]})
    return f


PELNE = {
    ID1.lower(): _pelny(ID1, "TYNK-MISTRZ USŁUGI REMONTOWE", "2026-09-20", email="Biuro@Tynk-Mistrz.pl", telefon="601-234-567",
                        www="WWW.TYNK-MISTRZ.PL", nip="5250000251"),
    ID2.lower(): _pelny(ID2, "MALARZ GLIWICE", "2015-03-01", kod="4334Z", email="malarz.gliwice@gmail.com", nip="9510001003"),
    ID3.lower(): _pelny(ID3, "STARE REMONTY", "2009-01-10", inne="4399Z", nip="7792142959"),
}


class FakeAPI:
    """Podmiana `ceidg._http`: dwie strony `/firmy`, szczegóły `/firma?ids=…`, wszystko zapisane do sprawdzenia."""

    def __init__(self, odpowiedzi=None, max_ids=25):
        self.wywolania: list[tuple[str, str]] = []
        self.odpowiedzi = list(odpowiedzi or [])         # (kod, treść, nagłówki) przed normalnymi odpowiedziami
        self.max_ids = max_ids

    def __call__(self, url, tok, timeout=60):
        self.wywolania.append((url, tok))
        if self.odpowiedzi:
            o = self.odpowiedzi.pop(0)
            if isinstance(o, Exception):
                raise o
            return o
        u = urllib.parse.urlsplit(url)
        q = urllib.parse.parse_qs(u.query)
        assert u.netloc == "dane.biznes.gov.pl" and tok == TOKEN and TOKEN not in url
        if u.path.endswith("/firmy"):
            strona = q.get("page", ["0"])[0]
            self_ = f"{API}/firmy?{u.query}"
            if strona == "0":
                dane = [_lista_wpis(ID1, "TYNK-MISTRZ USŁUGI REMONTOWE", "2026-09-20"),
                        _lista_wpis(ID2, "MALARZ GLIWICE", "2015-03-01")]
                nast = f"https://dane.biznes.gov.pl/api/ceidg/v3/firmy?{u.query}&page=1"
            else:
                dane = [_lista_wpis(ID3, "STARE REMONTY", "2009-01-10")]
                nast = self_                                       # ostatnia strona: next = self
            return 200, json.dumps({"firmy": dane, "count": 3, "links": {"self": self_, "next": nast}}), {}
        if u.path.endswith("/firma"):
            ids = q.get("ids", [])
            if len(ids) > self.max_ids:
                return 400, json.dumps({"code": "NIEPOPRAWNA_ILOSC_IDENTYFIKATOROW", "message": "za dużo"}), {}
            if "nip" in q:
                return 200, json.dumps({"firma": [PELNE[ID1.lower()]]}), {}
            return 200, json.dumps({"firma": [PELNE[i.lower()] for i in ids if i.lower() in PELNE]}), {}
        if "/firma/" in u.path:
            return 200, json.dumps({"firma": [PELNE[u.path.rsplit("/", 1)[1].lower()]]}), {}
        return 404, "", {}


@pytest.fixture
def api(monkeypatch):
    fake = FakeAPI()
    pauzy: list[float] = []
    monkeypatch.setenv("CEIDG_TOKEN", f"Bearer {TOKEN}\n")              # wklejony z prefiksem i końcem linii
    monkeypatch.setattr(ceidg, "_http", fake)
    monkeypatch.setattr(ceidg, "_spij", pauzy.append)
    monkeypatch.setattr(ceidg, "_dzis", lambda: dt.date(2026, 10, 5))
    fake.pauzy = pauzy
    return fake


def _bez_tokenu(*teksty):
    for t in teksty:
        assert TOKEN not in t and "podpis-testowy-ceidg" not in t


def test_search_paginates_and_maps_to_leads(api, tmp_path, capsys):
    out = tmp_path / "ceidg.jsonl"
    assert ceidg.main(["szukaj", "--pkd", "43.31.Z,4334Z", "--miasto", "Gliwice", "--woj", "PL24", "--limit", "10", "-o", str(out)]) == 0
    urle = [u for u, _ in api.wywolania]
    pierwsze = urllib.parse.parse_qs(urllib.parse.urlsplit(urle[0]).query)
    assert pierwsze == {"pkd": ["4331Z", "4334Z"], "miasto": ["Gliwice"], "wojewodztwo": ["śląskie"], "status": ["AKTYWNY"],
                        "limit": ["10"]}
    assert "page=1" in urle[1] and "/firma?" in urle[2] and len(urle) == 3     # strona 2 = ostatnia (next = self): koniec
    assert urllib.parse.parse_qs(urllib.parse.urlsplit(urle[2]).query)["ids"] == [ID1, ID2, ID3]
    assert api.pauzy and all(3.9 <= p <= ceidg.ODSTEP_S for p in api.pauzy) and len(api.pauzy) == 2   # przerwa między zapytaniami
    sygnaly = ll.czytaj_jsonl(str(out))
    assert [s["typ"] for s in sygnaly] == ["ceidg-nowa-firma", "ceidg-firma", "ceidg-firma"]
    s = sygnaly[0]
    assert s["data"] == "2026-09-20" and s["stan_na"] == "2026-10-05" and s["zrodlo"].endswith(f"/wpis/ceidg/{ID1}")
    assert s["opis"] == "rozpoczęła działalność 2026-09-20 (CEIDG, jednoosobowa): tynkowanie (PKD 43.31.Z)"
    assert s["firma"] == {"nazwa": "TYNK-MISTRZ USŁUGI REMONTOWE", "nip": "5250000251", "regon": "123456785", "woj": "ŚLĄSKIE",
                          "miejscowosc": "Gliwice", "pkd": "43.31.Z", "pkd_inne": ["43.34.Z"], "www": "www.tynk-mistrz.pl"}
    assert s["kontakty"] == [{"typ": "email", "wartosc": "biuro@tynk-mistrz.pl", "rodzaj": "ogolny", "zrodlo": s["zrodlo"]},
                             {"typ": "telefon", "wartosc": "+48 601 234 567", "zrodlo": s["zrodlo"]}]
    assert s["szczegoly"]["forma"] == "JEDNOOSOBOWA DZIAŁALNOŚĆ GOSPODARCZA" and s["szczegoly"]["rok_pkd"] == "2007"
    assert sygnaly[1]["kontakty"][0]["rodzaj"] == "osobowy"                   # skrzynka darmowa = dane osobowe
    err = capsys.readouterr().err
    assert "w rejestrze 3, pobrane 3, po filtrach 3" in err and "nowe firmy 1" in err and "art. 398 PKE" in err
    _bez_tokenu(err, out.read_text(encoding="utf-8"))

    # leady.py przyjmuje wiersze bez zmian: nowa firma to lead, sam wpis (ceidg-firma) nie jest powodem „dlaczego teraz”
    p = tmp_path / "leady"
    p.mkdir()
    (p / "ICP.yaml").write_text("nazwa: Remonty\ndopasowanie:\n  pkd: ['43.3']\n  woj: [ŚLĄSKIE]\n  slowa: [elewacje]\n  prog: 1.0\n",
                                encoding="utf-8")
    leady.cmd_dodaj(p, [str(out)])
    leady.cmd_ocen(p, top=10, monitoring=False, dzis=dt.date(2026, 10, 5))
    rows = list(csv.DictReader((p / "leady.csv").open(encoding="utf-8")))
    assert [r["klucz"] for r in rows] == ["nip:5250000251"]
    r = rows[0]
    assert r["niesprawdzone"] == "slowa" and r["dopasowanie"] == "1.0"       # opis wpisu w CEIDG to branża, nie potrzeba
    assert r["email"] == "biuro@tynk-mistrz.pl" and r["email_zrodlo"] == s["zrodlo"]
    assert r["telefon"] == "+48 601 234 567" and r["telefon_zrodlo"] == s["zrodlo"]
    md = (p / "LEADY.md").read_text(encoding="utf-8")
    assert "[CEIDG](https://www.biznes.gov.pl/pl/wyszukiwarka-firm/wpis/ceidg/" in md and "UŚUDE" in md


def test_private_data_never_leaves_the_script():
    f = ceidg.normalizuj(PELNE[ID1.lower()], "2026-10-05")
    s = ceidg.sygnal(f)
    tekst = json.dumps([f, s], ensure_ascii=False)
    for x in PRYWATNE:
        assert x not in tekst, x
    assert "44-100" not in tekst and "Zabrze" not in tekst and "Bytom" not in tekst   # ani adres korespondencyjny, ani kod
    assert set(f) == {"id", "nazwa", "nip", "regon", "status", "data_rozpoczecia", "data_zawieszenia", "data_wznowienia",
                      "miejscowosc", "gmina", "powiat", "woj", "pkd", "pkd_opis", "pkd_inne", "rok_pkd", "email", "email_typ",
                      "telefon", "www", "pelne", "zrodlo", "stan_na"}
    assert f["miejscowosc"] == "Gliwice" and f["powiat"] == "Gliwice"


def test_offline_from_file_without_token(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("CEIDG_TOKEN", raising=False)
    monkeypatch.setattr(ceidg, "_http", lambda *a, **k: pytest.fail("tryb offline nie może pytać sieci"))
    plik = tmp_path / "odpowiedz.json"
    plik.write_text(json.dumps({"firma": list(PELNE.values())}, ensure_ascii=False), encoding="utf-8")
    t = dt.datetime(2026, 10, 5, 12).timestamp()
    os.utime(plik, (t, t))
    assert ceidg.main(["szukaj", "--z-pliku", str(plik), "--pkd", "43.34.Z"]) == 0
    out, err = capsys.readouterr()
    wiersze = [json.loads(x) for x in out.splitlines()]
    assert [w["firma"]["nazwa"] for w in wiersze] == ["TYNK-MISTRZ USŁUGI REMONTOWE", "MALARZ GLIWICE"]   # 43.34.Z jako PKD dodatkowe
    assert all(w["stan_na"] == "2026-10-05" for w in wiersze) and "stan na 2026-10-05" in err
    assert ceidg.main(["firma", "--z-pliku", str(plik), "--json"]) == 0
    rekordy = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert len(rekordy) == 3 and all("pelne" not in r for r in rekordy)
    assert ceidg.main(["szukaj", "--z-pliku", str(tmp_path / "brak.json"), "--miasto", "X"]) == 2


def test_missing_token_exit_2_without_network(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("CEIDG_TOKEN", raising=False)
    monkeypatch.setattr(ceidg, "_http", lambda *a, **k: pytest.fail("bez tokenu nie pytamy API"))
    for argv in (["szukaj", "--pkd", "43.31.Z", "--miasto", "Gliwice"], ["firma", "--nip", "5250000251"], ["sprawdz"]):
        assert ceidg.main(argv) == 2
        err = capsys.readouterr().err
        assert "brak CEIDG_TOKEN" in err and "Klucze" in err and "jarvo-lowca" in err
    monkeypatch.setenv("CEIDG_TOKEN", "  ")
    assert ceidg.main(["sprawdz"]) == 2


def test_bad_input_exit_2_without_network(api, capsys):
    assert ceidg.main(["szukaj", "--pkd", "43", "--miasto", "Gliwice"]) == 2
    assert "pełne kody podklas" in capsys.readouterr().err
    assert ceidg.main(["szukaj", "--status", "AKTYWNY"]) == 2                     # sam status = cały rejestr
    assert ceidg.main(["szukaj", "--miasto", "Gliwice", "--status", "CZYNNY"]) == 2
    assert ceidg.main(["szukaj", "--miasto", "Gliwice", "--od-daty", "5.10.2026"]) == 2
    assert ceidg.main(["firma", "--nip", "5250000252"]) == 2                        # zła suma kontrolna
    assert ceidg.main(["firma", "--id", "../raporty"]) == 2
    assert api.wywolania == []


def test_401_retried_once_then_exit_2(api, monkeypatch, capsys):
    stary = _jwt(1_700_000_000)
    monkeypatch.setenv("CEIDG_TOKEN", stary)
    api.odpowiedzi = [(401, '{"message":"Unauthorized","http_status_code":401}', {})] * 2
    assert ceidg.main(["szukaj", "--pkd", "43.31.Z", "--miasto", "Gliwice"]) == 2
    assert len(api.wywolania) == 2 and all(t == stary for _, t in api.wywolania)
    err = capsys.readouterr().err
    assert "401" in err and "wygasł 2023-11-14" in err and "CEIDG_TOKEN" in err and stary not in err
    api.wywolania.clear()
    api.odpowiedzi = [(401, "", {})]                                               # chwilowe 401, potem normalnie
    monkeypatch.setenv("CEIDG_TOKEN", TOKEN)
    assert ceidg.main(["firma", "--nip", "5250000251"]) == 0 and len(api.wywolania) == 2
    api.wywolania.clear()
    api.odpowiedzi = [(403, "", {})]
    assert ceidg.main(["sprawdz"]) == 2 and len(api.wywolania) == 1               # 403: bez ponawiania
    assert "uprawnień" in capsys.readouterr().err


def test_429_waits_and_retries_then_stops(api, capsys):
    api.odpowiedzi = [(429, "", {"retry-after": "5"})]
    assert ceidg.main(["firma", "--nip", "5250000251"]) == 0
    assert len(api.wywolania) == 2 and ceidg.PAUZA_429_S in api.pauzy             # min. 180 s, nie 5 s z nagłówka
    capsys.readouterr()
    api.wywolania.clear()
    api.pauzy.clear()
    api.odpowiedzi = [(429, "", {})] * 3
    assert ceidg.main(["firma", "--nip", "5250000251"]) == 3
    assert len(api.wywolania) == 3 and api.pauzy.count(ceidg.PAUZA_429_S) == 2
    assert "limit zapytań (429)" in capsys.readouterr().err
    api.wywolania.clear()
    api.odpowiedzi = [(429, "", {"retry-after": "3600"})]                         # limit godzinowy: od razu stop
    assert ceidg.main(["firma", "--nip", "5250000251"]) == 3 and len(api.wywolania) == 1


def test_5xx_and_network_errors_retried(api, capsys):
    api.odpowiedzi = [(503, "", {}), ConnectionError("dane.biznes.gov.pl: timed out")]
    assert ceidg.main(["firma", "--nip", "5250000251"]) == 0
    assert len(api.wywolania) == 3 and [p for p in api.pauzy if p > ceidg.ODSTEP_S] == list(ceidg.PAUZY_5XX)
    assert "TYNK-MISTRZ" in capsys.readouterr().out
    api.odpowiedzi = [(500, "", {})] * 3
    assert ceidg.main(["firma", "--nip", "5250000251"]) == 1
    assert "po 3 próbach" in capsys.readouterr().err


def test_token_never_in_output_even_if_api_echoes_it(api, capsys):
    api.odpowiedzi = [(400, json.dumps({"code": "NIEPOPRAWNA_LISTA_PARAMETROW", "message": f"zły nagłówek Bearer {TOKEN}"}), {})]
    assert ceidg.main(["szukaj", "--pkd", "43.31.Z", "--miasto", "Gliwice"]) == 1
    out, err = capsys.readouterr()
    assert "NIEPOPRAWNA_LISTA_PARAMETROW" in err and "***" in err
    _bez_tokenu(out, err, repr(ceidg.Klient(TOKEN)))
    kl = ceidg.Klient(TOKEN)                                                      # linki z odpowiedzi tylko na host API
    assert kl.z_linku("https://zly.example.com/api/ceidg/v3/firmy?page=2") == f"{API}/firmy?page=2"
    assert kl.z_linku("https://dane.biznes.gov.pl/inne?page=2") is None and kl.z_linku(None) is None
    assert ceidg._BezPrzekierowan().redirect_request(None, None, 302, "", {}, "https://zly.example.com") is None


def test_details_batch_split_when_api_refuses_count(api):
    api.max_ids = 2
    kl = ceidg.Klient(TOKEN)
    dane = ceidg.szczegoly(kl, [ID1, ID2, ID3])
    assert set(dane) == {ID1.lower(), ID2.lower(), ID3.lower()}
    ids = [len(urllib.parse.parse_qs(urllib.parse.urlsplit(u).query)["ids"]) for u, _ in api.wywolania]
    assert ids == [3, 1, 1, 1]                                                     # 25 → … → 1: podział do skutku


def test_search_respects_limit_and_new_firm_rules(api, capsys):
    assert ceidg.main(["szukaj", "--miasto", "Gliwice", "--limit", "2", "--bez-szczegolow"]) == 0
    out, err = capsys.readouterr()
    assert len(out.splitlines()) == 2 and len(api.wywolania) == 1                  # limit 2: jedna strona, bez szczegółów
    assert "więcej niż --limit 2" in err and "--bez-szczegolow" in err
    assert all(json.loads(x)["kontakty"] == [] for x in out.splitlines())
    f = {"stan_na": "2026-10-05"}
    assert ceidg.nowa({**f, "data_rozpoczecia": "2026-09-05"}) and not ceidg.nowa({**f, "data_rozpoczecia": "2026-09-04"})
    planowana = ceidg.sygnal(ceidg.normalizuj({**PELNE[ID1.lower()], "dataRozpoczecia": "2026-10-12",
                                               "status": "OCZEKUJE_NA_ROZPOCZECIE_DZIALANOSCI"}, "2026-10-05"))
    assert planowana["typ"] == "ceidg-nowa-firma" and planowana["opis"].startswith("rozpocznie działalność 2026-10-12")
    assert ceidg._pkd("4331Z") == "43.31.Z" and ceidg._pkd(" 43.31.z ") == "43.31.Z"
