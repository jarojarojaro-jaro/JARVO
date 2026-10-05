"""Wideograf: pomiar animacji HTML (pomiar.py) na syntetycznych próbkach, bez przeglądarki; raport, odcisk, wyjątki."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profiles" / "jarvo-wideo" / "scripts"))

import pomiar as pm  # noqa: E402

HZ = 10.0
W, H = 1080, 1920


def tekst(id_, full, x0=100, y0=600, x1=900, y1=680, a=1.0, seen=None, color="rgb(255, 255, 255)", size=64, weight=700):
    return {"id": id_, "full": full, "seen": full if seen is None else seen, "a": a, "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "color": color, "size": size, "weight": weight, "family": "system-ui", "shadow": "", "stroke": ""}


def probki(dlugosc, teksty_w=lambda t: [], luma=lambda t: 0.5, zmiana=lambda t: 0.05, ruch=lambda t: 0.3):
    out = []
    for i in range(int(dlugosc * HZ)):
        t = round(i / HZ, 4)
        out.append({"t": t, "W": W, "H": H, "teksty": teksty_w(t), "luma": luma(t),
                    "zmiana": None if i == 0 else zmiana(t), "ruch": None if i == 0 else ruch(t)})
    return out


def kody(ust):
    return sorted((u["kod"], u["waga"]) for u in ust)


def test_czas_czytania_i_kolory():
    assert pm.czas_czytania("") == 0 and pm.czas_czytania("Kawa") == 0.73 and pm.czas_czytania("Kawa Jarvo") == 1.07
    assert pm.czas_czytania("Najlepsza kawa w mieście od 1998 roku") == round(0.4 + 7 / 3, 2)
    assert pm.czas_czytania("The best coffee in town", "en") < pm.czas_czytania("Najlepsza kawa w całym mieście")
    assert pm.czas_wygodny("") == 0 and pm.czas_wygodny("Ustaw stację") == round(11 / 15 + 1.5, 2)   # spacje się nie liczą
    assert pm.kolor_css("rgb(10, 20, 30)") == (10, 20, 30, 1.0) and pm.kolor_css("rgba(0, 0, 0, 0.5)")[3] == 0.5
    assert pm.kolor_css("rgb(1 2 3 / 40%)")[3] == 0.4 and pm.kolor_css("#fff") == (255, 255, 255, 1.0)
    assert pm.kolor_css("#22222280")[3] == pytest.approx(128 / 255) and pm.kolor_css("czerwony") is None
    assert pm.kontrast((0, 0, 0), (255, 255, 255)) == 21.0 and pm.kontrast((119, 119, 119), (255, 255, 255)) == pytest.approx(4.48, abs=0.01)
    assert pm.nalozony((255, 255, 255, 0.5), (0, 0, 0)) == (127.5, 127.5, 127.5)


def test_czysta_animacja_bez_ustalen():
    p = probki(5, lambda t: [tekst(1, "Kawa z palarni Jarvo")] if t >= 0.2 else [])
    assert pm.analiza(p, 5, HZ, "tiktok", "pl", {1: ((10, 15, 30), 2.0)}) == []


def test_czas_czytania_i_odslanianie():
    # tytuł 0,6 s → błąd; pisanie znak po znaku: liczy się tylko czas, gdy cały tekst jest odsłonięty
    pelny = "Najlepsza kawa w mieście od 1998 roku"
    def tt(t):
        out = [tekst(1, pelny)] if 0.5 <= t < 1.1 else []
        if 2.0 <= t < 6.0:
            n = min(len(pelny), int((t - 2.0) * 20))          # 20 znaków/s: cały po ~1,9 s
            out.append(tekst(2, pelny, seen=pelny[:n]))
        return out
    ust = pm.analiza(probki(7, tt), 7, HZ, None)
    cz = {u["tekst"] if u["od"] < 1 else "pisanie": u for u in ust if u["kod"] == "czas_czytania"}
    assert cz[pelny]["waga"] == "blad" and cz[pelny]["dostepny"] == pytest.approx(0.6)
    assert cz["pisanie"]["waga"] == "ostrz" and cz["pisanie"]["dostepny"] < cz["pisanie"]["potrzeba"]   # 4 s minus pisanie
    assert cz[pelny]["minimum"] == pm.czas_czytania(pelny) and cz[pelny]["potrzeba"] == pm.czas_wygodny(pelny)
    # dość dla szybkiego czytelnika (≥ 70% minimum), za mało na spokojne przeczytanie: ostrzeżenie, nie błąd
    krotko = pm.analiza(probki(4, lambda t: [tekst(1, "Ustaw stację")] if 1.0 <= t < 2.2 else []), 4, HZ, None)
    assert [(u["kod"], u["waga"]) for u in krotko] == [("czas_czytania", "ostrz")] and "spokojne" in krotko[0]["opis"]


def test_poza_kadrem_strefy_i_kontrast():
    def tt(t):
        return [tekst(1, "Superpromocja", x0=420, x1=1500, y0=1100, y1=1240, a=1.0) if 1.0 <= t < 2.0 else None,
                tekst(2, "Kod rabatowy KAWA10", y0=1640, y1=1700) if 3.0 <= t < 5.0 else None,
                tekst(3, "Zamów online", color="rgb(196, 196, 196)", size=40, weight=400)] if True else []
    p = probki(6, lambda t: [x for x in tt(t) if x])
    ust = pm.analiza(p, 6, HZ, "tiktok", "pl", {3: ((255, 255, 255), 2.0)})
    assert ("tekst_poza_kadrem", "blad") in kody(ust)
    strefy = [u for u in ust if u["kod"] == "strefa_platformy"]
    assert {u["tekst"] for u in strefy} == {"Superpromocja", "Kod rabatowy KAWA10"} and all(u["waga"] == "blad" for u in strefy)
    k = next(u for u in ust if u["kod"] == "kontrast")
    assert k["kontrast"] == pytest.approx(1.74, abs=0.01) and k["prog"] == 4.5
    # poziom 16:9 bez platformy: marginesy kadru tylko ostrzegają; duży tekst ma próg 3:1
    p2 = [{**x, "W": 1920, "H": 1080, "teksty": [tekst(4, "Tytuł", y0=20, y1=70, size=80, color="rgb(150,150,150)")]} for x in probki(2)]
    u2 = pm.analiza(p2, 2, HZ, None, "pl", {4: ((255, 255, 255), 1.0)})
    assert ("strefa_platformy", "ostrz") in kody(u2) and next(u for u in u2 if u["kod"] == "kontrast")["prog"] == 3.0


def test_cien_albo_obrys_ratuje_kontrast():
    x = tekst(1, "Biały tekst", color="rgb(255, 255, 255)")
    x["stroke"] = "rgb(0, 0, 0)"
    ust = pm.analiza(probki(2, lambda t: [x]), 2, HZ, None, "pl", {1: ((250, 250, 250), 1.0)})
    assert not [u for u in ust if u["kod"] == "kontrast"]


def test_obraz_czarna_przerwa_martwe_i_rytm():
    luma = lambda t: 0.01 if 3.0 <= t < 3.3 or t < 0.3 else 0.5            # czerń na starcie jest dozwolona
    ruch = lambda t: 0.0 if 4.0 <= t < 7.5 or t >= 9.0 else 0.3            # stoi 3,5 s w środku i na końcu
    ust = pm.analiza(probki(10, luma=luma, ruch=ruch), 10, HZ, None)
    czarne = [u for u in ust if u["kod"] == "czarna_przerwa"]
    assert len(czarne) == 1 and (czarne[0]["od"], czarne[0]["do"]) == (3.0, 3.3)
    martwe = [u for u in ust if u["kod"] == "martwy_odcinek"]
    assert len(martwe) == 1 and martwe[0]["od"] == pytest.approx(3.9) and "na końcu" not in martwe[0]["opis"]  # koniec 1 s: za krótko
    # rytm: zmiany co 1,0 s bez akcentu
    zm = lambda t: 0.2 if round(t * 10) % 10 == 5 else 0.01
    ust = pm.analiza(probki(12, zmiana=zm), 12, HZ, None)
    assert ("monotonny_rytm", "ostrz") in kody(ust)
    zm2 = lambda t: 0.2 if round(t * 10) in (5, 12, 31, 36, 58, 66, 95, 101) else 0.01
    assert "monotonny_rytm" not in [u["kod"] for u in pm.analiza(probki(12, zmiana=zm2), 12, HZ, None)]


def test_tlo_wokol_i_luma():
    Image = pytest.importorskip("PIL.Image")
    im = Image.new("RGB", (400, 200), (20, 40, 200))
    im.paste((255, 255, 255), (100, 80, 300, 120))          # „glify” w środku
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=95)
    bg = pm.tlo_wokol(buf.getvalue(), (100, 80, 300, 120))
    assert all(abs(a - b) < 12 for a, b in zip(bg, (20, 40, 200)))
    luma, zm, ruch, data = pm.luma_i_zmiana(buf.getvalue(), None)
    assert zm is None and ruch is None and 0 < luma < 1
    _, zm2, ruch2, _ = pm.luma_i_zmiana(buf.getvalue(), data)
    assert zm2 == 0 and ruch2 == 0


def test_odcisk_wyjatki_i_aktualnosc(tmp_path):
    anim = tmp_path / "anim.html"
    anim.write_text("<p>1</p>", encoding="utf-8")
    (tmp_path / "logo.svg").write_text("<svg/>", encoding="utf-8")
    ust = {"dlugosc": 6, "platforma": "tiktok"}
    o1 = pm.odcisk(anim, ust)
    (tmp_path / "pomiar.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pomiar.md").write_text("x", encoding="utf-8")
    (tmp_path / "film.mp4").write_bytes(b"x")
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "klatka.png").write_bytes(b"x")
    assert pm.odcisk(anim, ust) == o1                                        # raporty, wyjścia i out/ nie zmieniają odcisku
    assert pm.odcisk(anim, {**ust, "dlugosc": 7}) != o1
    (tmp_path / "logo.svg").write_text("<svg></svg>", encoding="utf-8")
    assert pm.odcisk(anim, ust) != o1                                        # zmiana assetu = nowy odcisk

    with pytest.raises(SystemExit, match="powód"):
        pm.wyjatki(["czas_czytania=bo"])
    wyj = pm.wyjatki(["czas_czytania@logo=znak marki, nie tekst do czytania"])
    u = [{"kod": "czas_czytania", "waga": "blad", "tekst": "Logo Jarvo"}, {"kod": "czas_czytania", "waga": "blad", "tekst": "Tytuł"}]
    pm.zastosuj_wyjatki(u, wyj)
    assert u[0]["wyjatek"] and "wyjatek" not in u[1] and pm.werdykt(u) == {"bledy": 1, "ostrzezenia": 0, "wyjatki": 1, "ok": False}

    raport = {"odcisk": pm.odcisk(anim, ust), "ustawienia": ust, "pokrycie": {"pelne": True, "tryb": "pelny", "hz": 10},
              "werdykt": {"ok": True, "bledy": 0}}
    assert pm.aktualnosc(anim, raport) == []
    assert any("niepełny" in p for p in pm.aktualnosc(anim, {**raport, "pokrycie": {"pelne": False, "tryb": "szybki", "hz": 4}}))
    assert any("błędy bez wyjątku: 2" in p for p in pm.aktualnosc(anim, {**raport, "werdykt": {"ok": False, "bledy": 2}}))
    anim.write_text("<p>2</p>", encoding="utf-8")
    assert any("zmieniły się" in p for p in pm.aktualnosc(anim, raport))


FAKTY = {"liczby": [{"id": "L1", "wartosc": "3,5 mln", "zrodla": [12], "tier": "B", "skala": "jeden co 9 s"}],
         "niepewne": ["40% klientów rezygnuje (jedno źródło)"]}


def test_liczby_na_ekranie_kontra_fakty(tmp_path):
    def teksty(t):
        out = [tekst(1, "3,5 mln bochenków rocznie")]
        if t < 1.0:                                                    # licznik w ruchu: każda wartość 0,1 s
            out.append(tekst(2, f"{int(t * 1000) + 517} zł", y0=800, y1=860))
        if 1.0 <= t < 2.0:
            out.append(tekst(3, "40% klientów odchodzi", y0=900, y1=960))
        if 2.0 <= t < 2.3:                                             # za krótko, żeby czytać: nie sprawdzamy
            out.append(tekst(4, "77 sekund", y0=1000, y1=1060))
        if t >= 3.0:
            out.append(tekst(5, "Krok 2: 12 dni czekania", y0=1100, y1=1160))
        return out
    u = pm.liczby_ekranu(probki(5, teksty), HZ, FAKTY)
    assert kody(u) == [("liczba_bez_zrodla", "ostrz"), ("liczba_niepewna", "blad")]
    n = next(x for x in u if x["kod"] == "liczba_niepewna")
    assert n["liczba"] == "40" and n["od"] == 1.0 and n["do"] == 2.0
    assert next(x for x in u if x["kod"] == "liczba_bez_zrodla")["liczba"] == "12"
    wyj = pm.wyjatki(["liczba_bez_zrodla@12 dni=numer kroku z planu, nie fakt do źródła"])
    pm.zastosuj_wyjatki(u, wyj)
    assert pm.werdykt(u) == {"bledy": 1, "ostrzezenia": 0, "wyjatki": 1, "ok": False}
    # odcisk: zmiana briefu albo brief dopisany po pomiarze = raport nieaktualny
    (tmp_path / "anim").mkdir()
    anim = tmp_path / "anim" / "anim.html"
    anim.write_text("<p>1</p>", encoding="utf-8")
    raport = {"ustawienia": {"dlugosc": 5}, "pokrycie": {"pelne": True}, "werdykt": {"ok": True}}
    raport["odcisk"] = pm.odcisk(anim, raport["ustawienia"])
    assert pm.aktualnosc(anim, raport) == []
    fakty = tmp_path / "fakty.json"
    fakty.write_text(json.dumps(FAKTY), encoding="utf-8")
    assert any("pomiar był bez niego" in x for x in pm.aktualnosc(anim, raport))
    ust = {"dlugosc": 5, "fakty": pm.fakty_info(fakty)}
    raport = {**raport, "ustawienia": ust, "odcisk": pm.odcisk(anim, ust)}
    assert pm.aktualnosc(anim, raport) == [] and pm.fakty_info(None) is None
    fakty.write_text(json.dumps({**FAKTY, "niepewne": []}), encoding="utf-8")
    assert any("fakty.json zmienił się" in x for x in pm.aktualnosc(anim, raport))


def test_podsumowanie_i_cli_html_wideo(tmp_path, monkeypatch):
    raport = {"plik": "anim.html", "werdykt": {"ok": False, "bledy": 1, "ostrzezenia": 1, "wyjatki": 1},
              "pokrycie": {"probek": 50, "hz": 10.0, "tryb": "pelny"}, "czcionki_brak": ["Brakujący"],
              "ustalenia": [{"kod": "martwy_odcinek", "waga": "ostrz", "opis": "obraz stoi", "poprawka": "ruch", "od": 3, "do": 7},
                            {"kod": "kontrast", "waga": "blad", "opis": "1.7:1", "poprawka": "tło", "od": 1, "do": 1.1},
                            {"kod": "czas_czytania", "waga": "blad", "opis": "logo", "poprawka": "-", "od": 0, "do": 1, "wyjatek": "znak marki"}]}
    md = pm.podsumowanie_md(raport)
    assert md.index("✗ 1.0") < md.index("⚠ 3.0") and "◇" in md and "kroje niedostępne: Brakujący" in md
    import importlib.util
    spec = importlib.util.spec_from_file_location("html_wideo", ROOT / "profiles" / "jarvo-wideo" / "scripts" / "html_wideo.py")
    hw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hw)
    anim = tmp_path / "anim.html"
    anim.write_text("<p>x</p>", encoding="utf-8")
    assert hw._raport_path(str(anim), None) == tmp_path / "pomiar.json"
    assert hw.main(["aktualny", str(anim)]) == 1                               # brak raportu
    ust = {"dlugosc": 6}
    (tmp_path / "pomiar.json").write_text(json.dumps({"odcisk": pm.odcisk(anim, ust), "ustawienia": ust,
                                                       "pokrycie": {"pelne": True}, "werdykt": {"ok": True}}), encoding="utf-8")
    assert hw.main(["aktualny", str(anim)]) == 0


def test_kompozycja_pusta_scena_oddech_i_uderzenia():
    """Kontrole z pomiaru przeglądarki (pola obiekt, czesc, powrot, do_poczatku); bez tych pól milczą."""
    def pr(dlugosc, obiekt=lambda t: 0.4, czesc=lambda t: 0.01, powrot=lambda t: 0.05, zmiana=lambda t: 0.0,
           do_poczatku=0.3, luma=lambda t: 0.5):
        out = probki(dlugosc, luma=luma, zmiana=zmiana)
        for p in out:
            p.update(obiekt=obiekt(p["t"]), czesc=czesc(p["t"]), powrot=powrot(p["t"]))
        out[-1]["do_poczatku"] = do_poczatku
        return out
    kody_ = lambda ust: [u["kod"] for u in ust]                                         # noqa: E731
    # spokojny film: ujęcie co 3 s, przed każdym 1,2 s spokoju, koniec stoi 1,5 s
    ruch = lambda t: 0.03 if (t % 3.0) < 1.6 and t < 7.5 else 0.0                       # noqa: E731
    ciecia = lambda t: 0.6 if round(t * 10) in (30, 60) else 0.01                       # noqa: E731
    assert pm.kompozycja(pr(9, czesc=ciecia, zmiana=ruch), 0.1) == []
    # pusta scena: obiekt 8% przez 2 s; krócej niż 1,5 s albo na czarnym: nic
    ust = pm.kompozycja(pr(6, obiekt=lambda t: 0.08 if 1.0 <= t < 3.0 else 0.4), 0.1)
    assert kody_(ust) == ["pusta_scena"] and (ust[0]["od"], ust[0]["do"]) == (1.0, 3.0)
    assert "pusta_scena" not in kody_(pm.kompozycja(pr(6, obiekt=lambda t: 0.08 if 1.0 <= t < 2.2 else 0.4), 0.1))
    assert "pusta_scena" not in kody_(pm.kompozycja(pr(6, obiekt=lambda t: 0.02, luma=lambda t: 0.01), 0.1))
    # cięcie 0,2 s po zatrzymaniu ruchu w ujęciu 4 s → bez_oddechu; szybki montaż (ujęcia < 2 s) nie
    ruch2 = lambda t: 0.03 if t < 3.8 or 4.0 <= t < 6.5 else 0.0                       # noqa: E731
    ust = pm.kompozycja(pr(8, czesc=lambda t: 0.6 if round(t * 10) == 40 else 0.01, zmiana=ruch2), 0.1)
    assert [u["chwile"] for u in ust if u["kod"] == "bez_oddechu"] == [[4.0]]
    # wyjście starego ujęcia (4,4–4,7 s) i wejście nowego (4,9 s) po 1,9 s spokoju: oddech był, przed przejściem
    wyjscie = lambda t: 0.03 if t < 2.5 or 4.4 <= t < 4.7 or t >= 4.8 else 0.0         # noqa: E731
    wejscie = lambda t: 0.6 if round(t * 10) == 49 else 0.01                           # noqa: E731
    assert "bez_oddechu" not in kody_(pm.kompozycja(pr(8, czesc=wejscie, zmiana=lambda t: wyjscie(t) if t < 7 else 0.0), 0.1))
    krotko = lambda t: 0.03 if t < 4.0 or 4.4 <= t < 4.7 or 4.8 <= t < 7 else 0.0      # noqa: E731
    assert [u["chwile"] for u in pm.kompozycja(pr(8, czesc=wejscie, zmiana=krotko), 0.1) if u["kod"] == "bez_oddechu"] == [[4.9]]
    montaz = lambda t: 0.6 if round(t * 10) in (12, 24, 36) else 0.01                  # noqa: E731
    assert pm.kompozycja(pr(6, czesc=montaz, zmiana=lambda t: 0.03 if t < 4.5 else 0.0), 0.1) == []
    # koniec: ruch do ostatniej klatki → ostrzeżenie; pętla (ostatnia = pierwsza) albo wygaszenie po spokoju: nic
    ust = pm.kompozycja(pr(5, zmiana=lambda t: 0.03), 0.1)
    assert [u["opis"] for u in ust] == ["koniec: ostatni kadr stoi 0.0 s"]
    assert pm.kompozycja(pr(5, zmiana=lambda t: 0.03, do_poczatku=0.0), 0.1) == []
    wygaszenie = lambda t: 0.5 if t < 4.5 else 0.5 - (t - 4.4)                        # noqa: E731
    assert pm.kompozycja(pr(5, zmiana=lambda t: 0.03 if t < 3.0 or t >= 4.5 else 0.0, luma=wygaszenie), 0.1) == []
    # uderzenia: 4 błyski, po których kadr wraca → ostrzeżenie; 3 wolno; zmiana bez powrotu to nie uderzenie
    blyski = lambda t: 0.7 if round(t * 10) in (10, 20, 30, 40) else 0.01             # noqa: E731
    stoi = lambda t: 0.0                                                                # noqa: E731
    ust = pm.kompozycja(pr(6, czesc=blyski, powrot=lambda t: 0.001, zmiana=lambda t: 0.2 if round(t * 10) in (10, 20, 30, 40) else 0.0), 0.1)
    assert [u["chwile"] for u in ust if u["kod"] == "uderzenia_kadru"] == [[1.0, 2.0, 3.0, 4.0]]
    trzy = lambda t: 0.7 if round(t * 10) in (10, 20, 30) else 0.01                   # noqa: E731
    assert pm.kompozycja(pr(6, czesc=trzy, powrot=lambda t: 0.001, zmiana=stoi), 0.1) == []
    # stare próbki bez pól kompozycji: kontrole milczą
    assert pm.kompozycja(probki(5), 0.1) == []


def test_obiekt_glowny_i_ruch_kadru():
    Image = pytest.importorskip("PIL.Image")
    ImageDraw = pytest.importorskip("PIL.ImageDraw")

    def jpg(rysuj, size=(1920, 1080), tlo=(245, 243, 238)):
        im = Image.new("RGB", size, tlo)
        rysuj(ImageDraw.Draw(im))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=90)
        return buf.getvalue()
    pusty = jpg(lambda d: d.rectangle((900, 500, 960, 560), fill=(20, 20, 20)))               # mała ikonka 60 px
    bohater = jpg(lambda d: d.ellipse((760, 240, 1160, 840), fill=(200, 30, 40)))           # koło 600 px
    napis = jpg(lambda d: [d.rectangle((300 + 170 * i, 470, 300 + 170 * i + 130, 600), fill=(10, 10, 10)) for i in range(8)])
    zdjecie = jpg(lambda d: [d.rectangle((0, y, 1920, y + 40), fill=((y * 7) % 255, 90, 160)) for y in range(0, 1080, 40)])
    assert pm.obiekt_glowny(pusty) < 0.08
    assert 0.5 <= pm.obiekt_glowny(bohater) <= 0.6
    assert pm.obiekt_glowny(napis) >= 0.15            # osiem „liter” w linii = jeden szeroki obiekt
    assert pm.obiekt_glowny(zdjecie) == 1.0
    assert pm.obiekt_glowny(jpg(lambda d: None)) == 0.0
    a, b = bytes([10] * 100), bytes([200] * 100)
    r = pm.ruch_kadru([a, a, b, a, a, a])             # błysk w próbce 2 i powrót
    assert r[0] == {} and r[1]["czesc"] == 0 and r[2]["czesc"] == 1.0 and r[2]["powrot"] == 0.0
    assert r[-1]["do_poczatku"] == 0.0
    assert pm.ruch_kadru([a, b, b, b])[1]["powrot"] == pytest.approx(190 / 255, abs=1e-4)   # nowe ujęcie: nie wraca
