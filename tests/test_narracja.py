"""film.py narracja (lektor z pliku narracji: pauzy z akapitów, oś czasu z chwilami po nazwie) i moduł strony
os_czasu.js. Synteza Edge TTS i ffmpeg są podmienione: sprawdzamy decyzje (parsowanie, układ osi, napisy, pliki)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO, load_script

wl = sys.modules.get("wideo_lib") or load_script("profiles/jarvo-wideo/scripts/wideo_lib.py", "wideo_lib")
film = load_script("profiles/jarvo-wideo/scripts/film.py", "jarvo_test_narracja_film")

NARRACJA = """// szkic dla piekarni
# Kolejka
Wchodzisz do piekarni o siódmej rano. | Przed tobą {kolejka}dziesięć osób.
Każda czeka trzy minuty.

W 2024 roku sprzedano {liczba}3,5 mln bochenków.{po}

# Skąd to się bierze
Skąd to się bierze?
"""


def mowa(slowa: list[str], sklej: str | None = None, krok: float = 0.3) -> dict:
    """Udawany wynik Edge TTS: słowo co `krok` s od 0,1 s, słyszalna mowa od 0,22 s; `sklej` skleja słowo z następnym
    tak jak Edge robi to z „2024 roku”."""
    ws, t, i = [], 0.1, 0
    while i < len(slowa):
        s = slowa[i]
        if sklej and s == sklej:
            s, i = f"{s} {slowa[i + 1]}", i + 1
        ws.append(wl.Word(round(t, 3), round(t + krok - 0.02, 3), s.rstrip(".?,")))
        t, i = t + krok, i + 1
    return {"od": 0.22, "do": ws[-1].end, "slowa": ws}


def test_parsowanie_narracji_rozdzialy_akapity_podzialy_chwile():
    n = film.parse_narracja(NARRACJA)
    assert n["bledy"] == []
    assert [r["tytul"] for r in n["rozdzialy"]] == ["Kolejka", "Skąd to się bierze"]
    assert [len(a) for r in n["rozdzialy"] for a in r["akapity"]] == [2, 1, 1]
    pierwsza = n["rozdzialy"][0]["akapity"][0][0]
    assert pierwsza["tekst"] == "Wchodzisz do piekarni o siódmej rano. Przed tobą dziesięć osób."   # bez | i {…}
    assert pierwsza["podzialy"] == [5, 9] and pierwsza["chwile"] == [("kolejka", 8)]
    trzecia = n["rozdzialy"][0]["akapity"][1][0]
    assert trzecia["chwile"] == [("liczba", 4), ("po", 7)]                 # {po} na końcu = koniec zdania
    assert any("kilka zdań" in o for o in n["ostrzezenia"])                 # dwa zdania w wierszu 3
    linie = film.linie_narracji(n)
    assert [(ln["id"], ln["pauza"]) for ln in linie] == [("u1.z1", "wstep"), ("u1.z2", "zdanie"), ("u2.z1", "akapit"),
                                                         ("u3.z1", "rozdzial")]


def test_parsowanie_bledy_i_ostrzezenia_tekstu():
    n = film.parse_narracja("{u3}Zle {a b}x {dup}a {dup}b {nie\n\n|\n")
    b = " ".join(n["bledy"])
    assert "{u3} zajęta" in b and "{a b}: nazwa" in b and "{dup} już jest" in b and "samo „{”" in b and "bez słów" in b
    dlugie = " ".join(["słowo"] * 21) + "."
    n = film.parse_narracja(f"{dlugie}\nA.\nB.\nC.\nD.\nKrótko, ale bardzo długi napis bez żadnego oddechu w środku | tak.")
    o = " ".join(n["ostrzezenia"])
    assert "21 słów" in o and "akapit ma 6 zdań" in o and "> 42): dodaj |" in o
    assert not film.parse_narracja("Było ok. 5 osób, m.in. Kasia. W 2024 r. Potem nic.")["ostrzezenia"][:0]
    assert film._kilka_zdan("Było ok. 5 osób, m.in. Kasia.") is False
    assert film._kilka_zdan("To jest jedno. To drugie.") is True
    assert film.parse_narracja("// sam komentarz\n\n# Tytuł bez zdań\n")["bledy"] == ["narracja bez zdań"]


def test_kontrola_tekstu_z_zasad_narracji():
    """Start od powitania albo definicji, akapity jak lista, lektor opisujący obraz, koniec, który streszcza, rozdział
    bez pytania; dobry tekst bez ostrzeżeń."""
    zly = ("Cześć, dziś opowiem o kolejkach.\nPo pierwsze piekarz.\n\nPo drugie klienci.\nNa ekranie widzisz wykres.\n\n"
           "# Drugi\nKolejny akapit.\n\nPodsumowując, kolejki są złe.\n")
    o = film.parse_narracja(zly)["ostrzezenia"]
    assert any("start od powitania" in x for x in o) and any("wiersze 4, 8: akapity zaczynają się jak lista" in x for x in o)
    assert any("opisuje obraz („Na ekranie”)" in x for x in o) and any("wiersz 10: koniec streszcza" in x for x in o)
    assert any("wiersz 5: rozdział 1 nie kończy się pytaniem" in x for x in o)
    assert "start od definicji" in film.parse_narracja("Kolejka to zjawisko społeczne.")["ostrzezenia"][0]
    assert "start od definicji" in film.parse_narracja("RAG, czyli wyszukiwanie przed odpowiedzią.")["ostrzezenia"][0]
    dobry = ("Wchodzisz do piekarni o siódmej rano.\nPrzed tobą dziesięć osób.\n\n# Dlaczego\nSkąd ta kolejka?\n\n"
             "# Mechanizm\nBo chleb kroi się dopiero przy ladzie.\nWięc każdy klient to minuta.\n")
    assert film.parse_narracja(dobry)["ostrzezenia"] == ["wiersz 2: rozdział 1 nie kończy się pytaniem, na które "
                                                          "odpowiada następny (zasada 9)"]
    assert film.parse_narracja(NARRACJA.replace("bochenków.{po}", "bochenków?{po}"))["ostrzezenia"] == [
        "wiersz 3: kilka zdań w jednej linii: każde zdanie w osobnej (pauzy i chwile liczone na linię)"]


def test_czasy_tokenow_po_literach_takze_w_sklejonym_slowie():
    tokeny = ["W", "2024", "roku", "sprzedano", "3,5", "mln"]
    slowa = [wl.Word(0.0, 0.1, "W"), wl.Word(0.1, 1.1, "2024 roku"), wl.Word(1.1, 1.5, "sprzedano"),
             wl.Word(1.5, 1.9, "3,5"), wl.Word(1.9, 2.3, "mln")]
    t = film.czasy_tokenow(tokeny, slowa)
    assert [k for *_, k in t] == [0, 1, 1, 2, 3, 4]
    assert t[1][0] == pytest.approx(0.1) and t[2][0] == pytest.approx(0.1 + 1.0 * 4 / 8)   # „roku” po 4 z 8 liter
    assert t[3][:2] == pytest.approx((1.1, 1.5))
    # Edge przeczytał inaczej (inne litery): proporcjonalnie, w kolejności
    inne = film.czasy_tokenow(["Ala", "ma", "kota"], [wl.Word(0, 1, "Alaa"), wl.Word(1, 2, "mma"), wl.Word(2, 3, "kotaa")])
    assert [k for *_, k in inne] == [0, 1, 2]
    assert film.czasy_tokenow(["a"], []) == [(0.0, 0.0, -1)]


def test_os_czasu_pauzy_ujecia_rozdzialy_chwile_i_napisy():
    n = film.parse_narracja(NARRACJA)
    linie = film.linie_narracji(n)
    os_ = film.uloz_os(linie, [mowa(ln["slowa"], "2024") for ln in linie], film.PAUZY, n["rozdzialy"])
    z = {x["id"]: x for x in os_["zdania"]}
    p = film.PAUZY
    assert z["u1.z1"]["start"] == p["wstep"]
    assert z["u1.z2"]["start"] == pytest.approx(z["u1.z1"]["koniec"] + p["zdanie"])     # pauza między słyszalną mową
    assert z["u2.z1"]["start"] == pytest.approx(z["u1.z2"]["koniec"] + p["akapit"])
    assert z["u3.z1"]["start"] == pytest.approx(z["u2.z1"]["koniec"] + p["rozdzial"])
    assert os_["dlugosc"] == pytest.approx(z["u3.z1"]["koniec"] + p["koniec"])
    u = {x["id"]: x for x in os_["ujecia"]}
    assert u["u1"]["start"] == 0 and u["u1"]["koniec"] == pytest.approx(z["u2.z1"]["start"] - film.CIECIE_PRZED)
    assert u["u2"]["start"] == u["u1"]["koniec"] and u["u3"]["koniec"] == os_["dlugosc"]
    assert [r["ujecia"] for r in os_["rozdzialy"]] == [["u1", "u2"], ["u3"]]
    c = os_["chwile"]
    assert c["u2"] == u["u2"]["start"] and c["u2.mowa"] == z["u2.z1"]["start"] and c["r2"] == u["u3"]["start"]
    assert c["po"] == z["u2.z1"]["koniec"] and c["koniec"] == os_["dlugosc"] and c["start"] == 0
    # {kolejka} przed 9. słowem: 0,1 + 8·0,3 w pliku, mowa od 0,22 → na osi start zdania + 2,28
    assert c["kolejka"] == pytest.approx(z["u1.z1"]["start"] + 0.1 + 8 * 0.3 - 0.22)
    assert c["liczba"] == pytest.approx(z["u2.z1"]["start"] + 0.1 + 3 * 0.3 - 0.22)      # 4. słowo Edge (sklejone 2024 roku)
    assert z["u1.z1"]["slowa"][0]["start"] == z["u1.z1"]["start"]                       # słowo przed mową przycięte
    assert [x["tekst"] for x in os_["napisy"]][:3] == ["Wchodzisz do piekarni o siódmej rano", "Przed tobą dziesięć osób",
                                                       "Każda czeka trzy minuty"]
    k = os_["_kawalki"][0]
    assert k["od"] == pytest.approx(0.2) and k["na"] == pytest.approx(p["wstep"] - film.ZAPAS_PRZED)
    assert [w.podzial for w in os_["_slowa"]][:10] == [False] * 5 + [True] + [False] * 3 + [True]


def test_podzial_w_napisach_srt_i_karaoke():
    slowa = [wl.Word(0, 0.3, "Przed"), wl.Word(0.3, 0.6, "tobą", True), wl.Word(0.6, 0.9, "dziesięć"), wl.Word(0.9, 1.2, "osób")]
    assert [len(g) for g in wl.chunk_words(slowa, 12, 42)] == [2, 2]
    bez = [wl.Word(w.start, w.end, w.text) for w in slowa]
    assert [len(g) for g in wl.chunk_words(bez, 12, 42)] == [4]
    assert "Przed tobą\n" in wl.build_srt(slowa)
    assert wl.align_display(slowa, "Przed tobą dziesięć osób.")[1].podzial is True


def test_kontrola_osi_tempo_krotkie_ujecia_rozdzialy_i_cel():
    n = film.parse_narracja(NARRACJA)
    linie = film.linie_narracji(n)
    os_ = film.uloz_os(linie, [mowa(ln["slowa"], "2024", krok=0.2) for ln in linie], film.PAUZY, n["rozdzialy"])
    assert film.tempo_narracji(os_) == pytest.approx(25 / (os_["zdania"][-1]["koniec"] - os_["zdania"][0]["start"]))
    o = " ".join(film.kontrola_osi(os_, (60, 90)))
    assert "słowa/s razem z pauzami (> 2.7)" in o and "u2 trwa" in o and "rozdziały i ich plansze dopiero od 3 min" in o
    assert "cel to 60–90 s: rozwiń" in o
    wolno = film.uloz_os(linie, [mowa(ln["slowa"], "2024", krok=0.45) for ln in linie], film.PAUZY, n["rozdzialy"])
    assert not any("słowa/s" in x for x in film.kontrola_osi(wolno, None))
    assert film._cel("60–90") == (60.0, 90.0) and film._cel("45") == (45.0, 45.0)
    assert film._pauzy("zdanie=0.4,akapit=1.2")["akapit"] == 1.2
    with pytest.raises(SystemExit):
        film._pauzy("oddech=1")


def test_cisza_z_logu_ffmpeg():
    log = ("[silencedetect] silence_start: 0\n[silencedetect] silence_end: 0.215 | silence_duration: 0.215\n"
           "silence_start: 1.18\nsilence_end: 1.21 | x\nsilence_start: 2.014\nsilence_end: 2.952 | x\n")
    assert film.cisza_z_logu(log, 2.952) == (0.215, 2.014)
    assert film.cisza_z_logu("silence_start: 0\nsilence_end: 0.2\nsilence_start: 2.0\n", 2.952) == (0.2, 2.0)
    assert film.cisza_z_logu("", 2.0) == (0.0, 2.0)                   # bez ciszy na brzegach: cały plik


def test_cmd_narracja_zapisuje_lektora_os_slowa_i_srt(tmp_path, monkeypatch, capsys):
    src = tmp_path / "narracja.txt"
    src.write_text(NARRACJA, encoding="utf-8")
    teksty = []

    def speak_many(items):
        teksty.extend(it["text"] for it in items)
        out = []
        for it in items:
            m = mowa(it["text"].split(), "2024")
            out.append(wl.Speech(tmp_path / "x.mp3", m["do"] + 0.9, m["slowa"]))
        return out
    zlozone = {}
    monkeypatch.setattr(film.wl, "speak_many", speak_many)
    monkeypatch.setattr(film.wl, "need", lambda tool: tool)
    monkeypatch.setattr(film, "granice_mowy", lambda sp: (0.22, sp.words[-1].end))
    monkeypatch.setattr(film, "zloz_lektor", lambda pliki, kaw, dl, out: (zlozone.update(n=len(kaw), dl=dl), out.write_bytes(b"RIFF")))
    out = tmp_path / "src" / "lektor.wav"
    assert film.main(["narracja", str(src), "-o", str(out), "--os", str(tmp_path / "src" / "anim" / "os_czasu.json"),
                      "--cel", "60-90"]) == 0
    raport = json.loads(capsys.readouterr().out)
    assert raport["ok"] and raport["zdania"] == 4 and raport["ujecia"] == 3 and raport["rozdzialy"] == 2
    assert teksty[0] == "Wchodzisz do piekarni o siódmej rano. Przed tobą dziesięć osób."
    os_ = json.loads((tmp_path / "src" / "anim" / "os_czasu.json").read_text(encoding="utf-8"))
    assert os_["wersja"] == 1 and os_["dlugosc"] == raport["dlugosc_s"] == zlozone["dl"] and zlozone["n"] == 4
    assert "_kawalki" not in os_ and "_slowa" not in os_ and "kolejka" in os_["chwile"]
    slowa = json.loads(out.with_suffix(".slowa.json").read_text(encoding="utf-8"))
    assert slowa[5] == {"start": slowa[5]["start"], "end": slowa[5]["end"], "text": "rano", "podzial": True}
    assert "podzial" not in slowa[0]
    assert out.with_suffix(".srt").read_text(encoding="utf-8").startswith("1\n")
    assert any("cel to 60–90" in o for o in raport["ostrzezenia"])
    assert raport["render"].endswith(f"--dlugosc {os_['dlugosc']:g}")
    # --sprawdz: bez syntezy, sam szacunek
    teksty.clear()
    assert film.main(["narracja", str(src), "--sprawdz"]) == 0
    r = json.loads(capsys.readouterr().out)
    assert teksty == [] and r["szacunek_s"] > 0 and r["slowa"] == 25
    zly = tmp_path / "zly.txt"
    zly.write_text("{u1}Nie.\n", encoding="utf-8")
    assert film.main(["narracja", str(zly), "-o", str(tmp_path / "z.wav")]) == 1
    assert teksty == []


def test_wymowa_terminow_lektor_czyta_inaczej_napis_zostaje():
    tts, mapa, uzyte = film.do_czytania(["Zbuduj", "to", "w", "„Next.js”,", "potem", "visual", "studio", "code."],
                                        {"Next.js": "nekst dżej es", "Visual Studio Code": "wiżual studio kołd"})
    assert tts == ["Zbuduj", "to", "w", "nekst", "dżej", "es,", "potem", "wiżual", "studio", "kołd."]
    assert mapa[3] == (3, 6, 0, 1) and mapa[5:] == [(7, 10, 0, 3), (7, 10, 1, 3), (7, 10, 2, 3)]
    assert sorted(uzyte) == ["Next.js", "Visual Studio Code"]
    assert film.do_czytania(["Ala", "ma", "kota."], None)[:2] == (["Ala", "ma", "kota."], [(0, 1, 0, 1), (1, 2, 0, 1), (2, 3, 0, 1)])
    n = film.parse_narracja("Zbuduj to w {nazwa}Next.js – szybko.\n")
    linie = film.linie_narracji(n, {"next.js": "nekst dżej es"})
    assert linie[0]["tts"] == "Zbuduj to w nekst dżej es – szybko." and linie[0]["wymowa"] == ["next.js"]
    os_ = film.uloz_os(linie, [mowa(ln["tts_slowa"]) for ln in linie], film.PAUZY, n["rozdzialy"])
    slowa = os_["_slowa"]
    assert [w.text for w in slowa] == ["Zbuduj", "to", "w", "Next.js", "szybko"]            # pisownia z tekstu, bez „–”
    z0 = os_["zdania"][0]["start"]
    assert slowa[3].start == pytest.approx(z0 + 0.1 + 3 * 0.3 - 0.22)                     # od „nekst”
    assert slowa[3].end == pytest.approx(z0 + 0.1 + 5 * 0.3 + 0.28 - 0.22)                # do końca „es”
    assert os_["chwile"]["nazwa"] == slowa[3].start
    assert os_["napisy"][0]["tekst"] == "Zbuduj to w Next.js szybko"


FAKTY = {"temat": "kolejka w piekarni",
         "liczby": [{"id": "L1", "wartosc": "3,5 mln", "jednostka": "bochenków", "twierdzenie": "sprzedano w 2024",
                     "zrodla": [12], "tier": "B", "skala": "jeden co 9 sekund", "data": "2024"}],
         "slowniczek": [{"termin": "bochenków", "prosto": "chleb", "wymowa": "bo-chen-kuf"}],
         "niepewne": ["ok. 40 osób dziennie rezygnuje z kolejki (jedno źródło D)"]}


def test_liczby_lektora_kontra_fakty():
    pewne, niepewne = wl.liczby_faktow(FAKTY)
    assert {3.5, 2024.0, 9.0} <= pewne and 12.0 not in pewne and niepewne == {40.0}
    assert wl.sprawdz_liczby("Jeden bochenek co 9 sekund, 3 razy", pewne, niepewne) == []
    assert wl.sprawdz_liczby("40 osób odchodzi, a 12 wraca", pewne, niepewne) == [("40", "niepewna"), ("12", "brak")]
    n = film.parse_narracja("Rano stoi 40 osób.\nW 2024 roku sprzedano 3,5 mln bochenków.\nCzeka 7 minut.\n")
    bledy, ostrz = film.kontrola_liczb(film.linie_narracji(n), FAKTY)
    assert len(bledy) == 1 and "wiersz 1: liczba „40” jest na liście niepewnych" in bledy[0]
    assert len(ostrz) == 1 and "wiersz 3: liczba „7” bez źródła" in ostrz[0]


def test_cmd_narracja_z_faktami_i_wymowa(tmp_path, monkeypatch, capsys):
    (tmp_path / "fakty.json").write_text(json.dumps(FAKTY, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "wideo").mkdir()
    src = tmp_path / "wideo" / "narracja.txt"                         # fakty.json katalog wyżej: znaleziony sam
    src.write_text(NARRACJA, encoding="utf-8")
    assert film.main(["narracja", str(src), "--sprawdz"]) == 0
    r = json.loads(capsys.readouterr().out)
    assert r["fakty"] == (tmp_path / "fakty.json").as_posix() and r["wymowa"] == ["bochenków"]   # ścieżka z „/”
    assert not any("bez źródła" in o for o in r["ostrzezenia"])       # 2024 i 3,5 mln są w faktach
    teksty = []

    def speak_many(items):
        teksty.extend(it["text"] for it in items)
        return [wl.Speech(tmp_path / "x.mp3", 3.0, mowa(it["text"].split(), "2024")["slowa"]) for it in items]
    monkeypatch.setattr(film.wl, "speak_many", speak_many)
    monkeypatch.setattr(film.wl, "need", lambda tool: tool)
    monkeypatch.setattr(film, "granice_mowy", lambda sp: (0.22, sp.words[-1].end))
    monkeypatch.setattr(film, "zloz_lektor", lambda pliki, kaw, dl, out: out.write_bytes(b"RIFF"))
    wymowa = tmp_path / "wymowa.json"
    wymowa.write_text(json.dumps({"bochenków": "bochenkuw"}), encoding="utf-8")
    out = tmp_path / "wideo" / "lektor.wav"
    assert film.main(["narracja", str(src), "-o", str(out), "--wymowa", str(wymowa)]) == 0
    capsys.readouterr()
    assert teksty[2] == "W 2024 roku sprzedano 3,5 mln bochenkuw."     # --wymowa nadpisuje słowniczek
    assert "bochenków" in out.with_suffix(".srt").read_text(encoding="utf-8")
    # liczba z listy niepewnych zatrzymuje syntezę
    teksty.clear()
    src.write_text("Rano w kolejce stoi 40 osób.\n", encoding="utf-8")
    assert film.main(["narracja", str(src), "-o", str(out)]) == 1
    r = json.loads(capsys.readouterr().out)
    assert teksty == [] and not r["ok"] and "niepewnych" in r["bledy"][0]
    # bez fakty.json (ani obok, ani katalog wyżej) nie ma kontroli liczb ani wymowy
    bez = tmp_path / "inny" / "wideo" / "narracja.txt"
    bez.parent.mkdir(parents=True)
    bez.write_text("Rano w kolejce stoi 40 osób.\n", encoding="utf-8")
    assert film.main(["narracja", str(bez), "--sprawdz"]) == 0
    r = json.loads(capsys.readouterr().out)
    assert r["ok"] and r["fakty"] is None and r["wymowa"] == []


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="brak ffmpeg")
def test_zloz_lektor_wkleja_wycinki_co_do_probki(tmp_path):
    import array
    import wave
    ton = tmp_path / "ton.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "sine=f=440:d=1", "-ar", "48000", "-ac", "1",
                    str(ton)], check=True)
    out = tmp_path / "lektor.wav"
    film.zloz_lektor([ton, ton], [{"od": 0.0, "do": 0.5, "na": 0.25}, {"od": 0.5, "do": 1.0, "na": 1.5}], 2.5, out)
    with wave.open(str(out)) as f:
        assert f.getframerate() == 48000 and f.getnframes() == 120000
        a = array.array("h", f.readframes(f.getnframes()))
    glosno = [i for i in range(0, len(a), 480) if max(abs(x) for x in a[i:i + 480]) > 1000]
    assert glosno[0] == 12000 and 36000 - 480 <= glosno[glosno.index(max(i for i in glosno if i < 60000))] <= 36000
    assert min(i for i in glosno if i >= 60000) == 72000


@pytest.mark.skipif(not shutil.which("node"), reason="brak node")
def test_modul_os_czasu_js(tmp_path):
    """bit() po nazwie z przesunięciem, nieznana nazwa = błąd z podpowiedzią, postęp między chwilami, ujęcie
    i napis w chwili t."""
    dane = {"dlugosc": 10, "chwile": {"start": 0, "u1": 0, "u1.koniec": 4, "u2": 4, "u2.z1": 4.5, "licznik": 6, "koniec": 10},
            "ujecia": [{"id": "u1", "start": 0, "koniec": 4}, {"id": "u2", "start": 4, "koniec": 10}],
            "napisy": [{"start": 4.5, "koniec": 6.5, "tekst": "Dziesięć osób"}]}
    skrypt = tmp_path / "t.mjs"
    skrypt.write_text("""
import { osZDanych } from %s;
const O = osZDanych(%s);
let blad = '';
try { O.bit('u2.z9'); } catch (e) { blad = e.message; }
let pusty = '';
try { osZDanych({}); } catch (e) { pusty = e.message; }
console.log(JSON.stringify({
  bit: [O.bit('u2.z1'), O.bit('licznik', -0.1)], blad, pusty,
  postep: [O.postep(3, 'u2', 'licznik'), O.postep(5, 'u2', 'licznik'), O.postep(7, 'u2', 6)],
  ujecie: [O.ujecie(1).id, O.ujecie(4).id, O.ujecie(99).id], napis: [O.napis(5)?.tekst, O.napis(1)],
  uzyte: O.uzyte().sort(), dl: O.dlugosc,
}));
""" % (json.dumps((REPO / "profiles/jarvo-wideo/scripts/os_czasu.js").as_uri()), json.dumps(dane)), encoding="utf-8")
    w = json.loads(subprocess.run(["node", str(skrypt)], capture_output=True, text=True, encoding="utf-8", check=True).stdout)
    assert w["bit"] == [4.5, pytest.approx(5.9)] and w["dl"] == 10
    assert "nieznana chwila „u2.z9”" in w["blad"] and "u2.z1" in w["blad"]
    assert "film.py narracja" in w["pusty"]
    assert w["postep"] == [0, 0.5, 1] and w["ujecie"] == ["u1", "u2", "u2"] and w["napis"] == ["Dziesięć osób", None]
    assert w["uzyte"] == ["licznik", "u2", "u2.z1"]


def test_modul_os_czasu_jest_kopiowany_pod_lib_jarvo():
    nz = load_script("profiles/jarvo-wideo/scripts/narzedzia.py")
    assert "os_czasu.js" in nz.JARVO_JS_PLIKI
    assert (REPO / "profiles/jarvo-wideo/scripts/os_czasu.js").is_file()
    assert Path(film.__file__).name == "film.py"
