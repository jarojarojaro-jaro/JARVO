"""zrodlo.py (Łowca, rozpoznanie źródła): analiza HAR, różnice dwóch nagrań, schemat sumy odpowiedzi; bez sieci."""

from __future__ import annotations

import base64
import json
import sys
import urllib.robotparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profiles" / "jarvo-lowca" / "scripts"))
import strona  # noqa: E402
import zrodlo  # noqa: E402


def _wpis(url, odp, metoda="GET", typ="application/json", rtyp="fetch", cialo=None, naglowki=None, status=200, b64=False):
    tekst = odp if isinstance(odp, str) else json.dumps(odp)
    content = {"mimeType": typ, "size": len(tekst), "text": base64.b64encode(tekst.encode()).decode() if b64 else tekst}
    if b64:
        content["encoding"] = "base64"
    req = {"method": metoda, "url": url, "headers": []}
    if cialo is not None:
        req["postData"] = {"mimeType": "application/json", "text": json.dumps(cialo)}
    return {"_resourceType": rtyp, "request": req,
            "response": {"status": status, "headers": [{"name": k, "value": v} for k, v in (naglowki or {}).items()], "content": content}}


def _har(tmp_path: Path, nazwa: str, strona_nr: int) -> Path:
    firmy = [{"id": 100 + strona_nr * 10 + i, "nazwa": f"Firma {strona_nr}-{i}", "nip": "9510001003"} for i in range(3)]
    entries = [
        _wpis("https://katalog.pl/szukaj?q=dachy", '<html><script id="__NEXT_DATA__" type="application/json">{"props": {"a": 1}}'
              "</script></html>", typ="text/html", rtyp="document"),
        _wpis("https://katalog.pl/_next/static/app.js", "x()", typ="application/javascript", rtyp="script"),
        _wpis("https://www.google-analytics.com/g/collect?v=2", {}, rtyp="fetch"),
        _wpis("https://px.example.com/api/v1/intent_pixel/track_request?app=1", {"ok": 1}, metoda="POST"),   # piksel spoza listy
        _wpis("https://ct.example.com/v3/?event=init", "GIF89a", typ="image/gif"),
        _wpis(f"https://api.katalog.pl/v1/szukaj?q=dachy&strona={strona_nr}&typ=dachowka",   # typ odbity w meta: nie zależność
              {"wyniki": firmy, "razem": 40, "kursor": "c-77a9f1e2", "meta": {"typ": "dachowka"}},
              naglowki={"ETag": f'"v{strona_nr}"', "Cache-Control": "max-age=60"}, b64=True),
        _wpis("https://api.katalog.pl/v1/firma/110", {"id": 110}, metoda="POST", cialo={"kursor": "c-77a9f1e2", "typ": "dachowka"}),
    ]
    p = tmp_path / nazwa
    p.write_text(json.dumps({"log": {"version": "1.2", "entries": entries}}), encoding="utf-8")
    return p


def test_har_summary_data_requests_incremental_and_dependencies(tmp_path):
    a = zrodlo.analiza_har(_har(tmp_path, "a.har", 1))
    assert a["zadan"] == 7 and [w["szablon"] for w in a["dane"]] == ["api.katalog.pl/v1/szukaj", "api.katalog.pl/v1/firma/{id}"]
    szukaj = a["dane"][0]
    assert szukaj["parametry"] == {"q": "dachy", "strona": "1", "typ": "dachowka"} and szukaj["przyrostowo"] == {"etag": '"v1"', "cache-control": "max-age=60"}
    assert szukaj["odpowiedz"] == "{wyniki: [3× {id: liczba, nazwa: tekst, nip: tekst}], razem: liczba, kursor: tekst, meta: {typ: tekst}}"   # base64
    assert a["zaleznosci"] == [{"zadanie": "POST api.katalog.pl/v1/firma/{id}", "pole": "kursor", "z_odpowiedzi": "GET api.katalog.pl/v1/szukaj"}]
    assert a["dokumenty"][0]["ukryte"][0]["skad"] == "next-data" and not a["odmowy"]


def test_har_diff_one_variable(tmp_path, capsys):
    r = zrodlo.roznice(_har(tmp_path, "a.har", 1), _har(tmp_path, "b.har", 2))
    p = {x["zadanie"]: x for x in r["pary"]}
    s = p["GET api.katalog.pl/v1/szukaj"]
    assert s["parametry"]["zmienione"] == {"strona": ["1", "2"]} and not s["parametry"]["tylko_a"]
    assert s["odpowiedz"]["a"] == s["odpowiedz"]["b"] and s["odpowiedz"]["zmienione_pola"] == "6 z 12"   # id i nazwy 3 firm
    assert "POST api.katalog.pl/v1/firma/{id}" not in p                     # to samo żądanie bez zmian
    assert not r["tylko_a"] and not r["tylko_b"]
    zrodlo.drukuj_roznice(r)
    assert "parametr strona: 1 → 2" in capsys.readouterr().out


def test_union_schema_optional_null_inconsistent(tmp_path):
    docs = [{"firmy": [{"id": 1, "nazwa": "A", "email": "biuro@a.pl", "tel": "601 222 333"}, {"id": "2", "nazwa": "B", "www": None}]},
            {"firmy": [{"id": 3, "nazwa": "C", "www": "https://c.pl", "dodano": "2026-09-29T10:00:08+00:00"}], "nastepna": None}]
    (tmp_path / "odp").mkdir()
    for i, d in enumerate(docs):
        (tmp_path / "odp" / f"{i}.json").write_text(json.dumps(d), encoding="utf-8")
    s = zrodlo.schemat_zrodel([str(tmp_path / "odp")])
    assert s["zadanie"] == "pliki JSON"
    pola = {p["sciezka"]: p for p in s["pola"]}
    assert s["dokumentow"] == 2 and "mało próbek (2)" in s["uwaga"]
    assert pola["$.firmy[].id"]["niespojne"] and pola["$.firmy[].id"]["typy"] == {"liczba": 2, "tekst": 1}
    assert pola["$.firmy[].www"]["opcjonalne"] and (pola["$.firmy[].www"]["obecne"], pola["$.firmy[].www"]["obiektow"]) == (2, 3)
    assert pola["$.firmy[].www"]["null_proc"] == 50 and pola["$.nastepna"]["opcjonalne"]
    assert not pola["$.firmy[].nazwa"]["opcjonalne"] and not pola["$.firmy[].nazwa"]["niespojne"]
    assert pola["$.firmy[].email"]["przyklady"] == ["<e-mail>"] and pola["$.firmy[].tel"]["przyklady"] == ["<numer>"]
    assert pola["$.firmy[].dodano"]["przyklady"] == ["2026-09-29T10:00:08+00:00"]       # data to nie telefon
    assert s["podsumowanie"]["niespojnych"] == 1


def test_record_respects_robots_and_blocks(tmp_path, monkeypatch, capsys):
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(["User-agent: *", "Disallow: /szukaj"])
    monkeypatch.setattr(strona, "robots", lambda url: rp)
    wywolania = []
    monkeypatch.setattr(zrodlo.subprocess, "run", lambda *a, **kw: wywolania.append(a))
    assert zrodlo.nagraj("katalog.pl/szukaj?q=x", str(tmp_path / "a.har")) == 3 and not wywolania
    assert "robots.txt nie pozwala" in capsys.readouterr().err
    har = tmp_path / "odm.har"
    har.write_text(json.dumps({"log": {"entries": [_wpis("https://api.x.pl/v1/lista", {"blad": 1}, status=429)]}}), encoding="utf-8")
    assert zrodlo.main(["har", str(har)]) == 3 and "odmowa" in capsys.readouterr().out


def test_diff_pairs_repeated_request_by_params(tmp_path):
    def har(nazwa, kolejnosc):
        wpisy = {"licznik": _wpis("https://api.k.pl/v1/szukaj?per_page=1&facet=region", {"razem": 40}),
                 "lista": _wpis(f"https://api.k.pl/v1/szukaj?per_page=20&page={1 if nazwa == 'a' else 2}", {"wyniki": [1, 2]})}
        p = tmp_path / f"{nazwa}.har"
        p.write_text(json.dumps({"log": {"entries": [wpisy[k] for k in kolejnosc]}}), encoding="utf-8")
        return p
    r = zrodlo.roznice(har("a", ["licznik", "lista"]), har("b", ["lista", "licznik"]))   # inna kolejność w nagraniu b
    assert [(x["zadanie"], x["parametry"]["zmienione"]) for x in r["pary"]] == [("GET api.k.pl/v1/szukaj (2. wywołanie)", {"page": ["1", "2"]})]


def test_schema_per_request_from_har(tmp_path, capsys):
    a, b = _har(tmp_path, "a.har", 1), _har(tmp_path, "b.har", 2)
    lista = zrodlo.schemat_zrodel([str(a), str(b)])                      # dwa żądania z danymi: lista do wyboru
    assert lista["zadania"] == [{"zadanie": "GET api.katalog.pl/v1/szukaj", "odpowiedzi": 2},
                                {"zadanie": "POST api.katalog.pl/v1/firma/{id}", "odpowiedzi": 2}]
    s = zrodlo.schemat_zrodel([str(a), str(b)], "/v1/szukaj")
    assert s["zadanie"] == "GET api.katalog.pl/v1/szukaj" and s["dokumentow"] == 2
    assert {p["sciezka"] for p in s["pola"]} >= {"$.wyniki[].nip", "$.kursor"} and "$.id" not in {p["sciezka"] for p in s["pola"]}
    assert zrodlo.main(["schemat", str(a), "--zadanie", "nie-ma"]) == 1 and "brak odpowiedzi JSON" in capsys.readouterr().out
