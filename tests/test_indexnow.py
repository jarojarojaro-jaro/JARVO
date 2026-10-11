"""indexnow.py (jarvo-web): plik klucza, adresy z sitemapy, zgłoszenie tylko dla produkcji."""

from __future__ import annotations

import argparse
import gzip

from conftest import load_script

ix = load_script("profiles/jarvo-web/scripts/indexnow.py")

KLUCZ = "0123456789abcdef0123456789abcdef"


def test_klucz_tworzy_plik_i_nie_nadpisuje(tmp_path):
    klucz, plik, nowy = ix.utworz_klucz(tmp_path / "public")
    assert nowy and plik.name == f"{klucz}.txt" and plik.read_text().strip() == klucz
    assert ix.KLUCZ_WZOR.match(klucz) and len(klucz) == 32
    (tmp_path / "public" / "robots.txt").write_text("User-agent: *\n")
    assert ix.utworz_klucz(tmp_path / "public") == (klucz, plik, False)
    # plik .txt o innej treści niż nazwa nie jest kluczem
    (tmp_path / "inne").mkdir()
    (tmp_path / "inne" / f"{KLUCZ}.txt").write_text("cos innego")
    assert ix.znajdz_klucz(tmp_path / "inne") is None


def serwer(pliki: dict[str, bytes]):
    def pobierz(url, limit=ix.LIMIT_MAPY):
        return (200, pliki[url][:limit]) if url in pliki else (404, b"")
    return pobierz


def mapa(*adresy) -> bytes:
    return ("<urlset>" + "".join(f"<url><loc>{a}</loc></url>" for a in adresy) + "</urlset>").encode()


def args(**kw):
    baza = dict(strona="https://nova.pl", katalog=None, klucz=KLUCZ, url=None, na_sucho=False)
    return argparse.Namespace(**(baza | kw))


def test_adresy_z_indeksu_sitemap_astro_i_gzip():
    pliki = {
        "https://nova.pl/robots.txt": b"User-agent: *\nSitemap: https://nova.pl/sitemap-index.xml\n",
        "https://nova.pl/sitemap-index.xml": b"<sitemapindex><sitemap><loc>https://nova.pl/sitemap-0.xml</loc></sitemap>"
                                             b"<sitemap><loc>https://nova.pl/blog.xml.gz</loc></sitemap>"
                                             b"<sitemap><loc>https://obca.pl/x.xml</loc></sitemap></sitemapindex>",
        "https://nova.pl/sitemap-0.xml": mapa("https://nova.pl/", "https://nova.pl/oferta/?a=1&amp;b=2"),
        "https://nova.pl/blog.xml.gz": gzip.compress(mapa("https://nova.pl/blog/", "https://nova.pl/")),
    }
    adresy, przeczytane = ix.adresy_z_sitemap("https://nova.pl", serwer(pliki))
    assert adresy == ["https://nova.pl/", "https://nova.pl/oferta/?a=1&b=2", "https://nova.pl/blog/"]
    assert "https://obca.pl/x.xml" not in przeczytane and len(przeczytane) == 3


def test_zglos_wysyla_tylko_adresy_hosta_po_sprawdzeniu_klucza():
    pliki = {"https://nova.pl/sitemap.xml": mapa("https://nova.pl/", "https://www.nova.pl/x", "https://nova.pl/kontakt/"),
             f"https://nova.pl/{KLUCZ}.txt": KLUCZ.encode() + b"\n"}
    wyslane = []

    def wyslij(host, klucz, adresy):
        wyslane.append((host, klucz, adresy))
        return [{"adresy": len(adresy), "status": 202, "opis": ix.ODPOWIEDZI[202]}]

    w = ix.zglos(args(), serwer(pliki), wyslij)
    assert not w["errors"] and w["adresy"] == 2
    assert wyslane == [("nova.pl", KLUCZ, ["https://nova.pl/", "https://nova.pl/kontakt/"])]
    assert any("www.nova.pl" in t for t in w["warnings"])


def test_zglos_bez_pliku_klucza_na_stronie_nic_nie_wysyla():
    pliki = {"https://nova.pl/sitemap.xml": mapa("https://nova.pl/")}
    w = ix.zglos(args(), serwer(pliki), lambda *a: (_ for _ in ()).throw(AssertionError("wysłane")))
    assert any("nie zwraca klucza" in t for t in w["errors"])


def test_zglos_na_sucho_i_bledy_odpowiedzi():
    pliki = {"https://nova.pl/sitemap.xml": mapa("https://nova.pl/"), f"https://nova.pl/{KLUCZ}.txt": KLUCZ.encode()}
    w = ix.zglos(args(na_sucho=True), serwer(pliki), lambda *a: (_ for _ in ()).throw(AssertionError("wysłane")))
    assert not w["errors"] and w["przyklady"] == ["https://nova.pl/"]
    w = ix.zglos(args(), serwer(pliki), lambda *a: [{"adresy": 1, "status": 403, "opis": ix.ODPOWIEDZI[403]}])
    assert w["errors"] == ["IndexNow HTTP 403: klucz nieważny (brak pliku klucza albo inna treść)"]


def test_zglos_odrzuca_podglady_i_brak_klucza(tmp_path):
    for strona in ("http://nova.pl", "https://localhost:4321", "https://127.0.0.1",
                   "https://abc-def.trycloudflare.com"):
        assert ix.zglos(args(strona=strona), serwer({}), None)["errors"], strona
    w = ix.zglos(args(klucz=None, katalog=str(tmp_path)), serwer({}), None)
    assert any("brak klucza" in t for t in w["errors"])
    ix.utworz_klucz(tmp_path)
    w = ix.zglos(args(klucz=None, katalog=str(tmp_path)), serwer({}), None)
    assert any("brak sitemapy" in t for t in w["errors"])


def test_url_reczne_i_kod_wyjscia(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(ix, "pobierz", serwer({f"https://nova.pl/{KLUCZ}.txt": KLUCZ.encode()}))
    monkeypatch.setattr(ix, "wyslij", lambda host, klucz, adresy: [{"adresy": len(adresy), "status": 200, "opis": "przyjęte"}])
    assert ix.main(["zglos", "nova.pl", "--klucz", KLUCZ, "--url", "https://nova.pl/nowy/"]) == 0
    assert "HTTP 200 (1 adresów)" in capsys.readouterr().out
    assert ix.main(["klucz", str(tmp_path), "--json"]) == 0
