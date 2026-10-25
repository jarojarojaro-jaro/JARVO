"""Polski lektor lokalny (jarvo-tts, głosy pl-PL-Matcha-*): normalizator tekstu, tablica symboli, podział na zdania.

Fonemizer (espeak-ng) i model ONNX są tylko w obrazie; tu sprawdzamy część w czystym Pythonie. Próba mowy obu głosów
idzie przy budowie obrazu (`jarvo-tts --sprawdz` w infra/Dockerfile).
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "infra" / "bin"
sys.path.insert(0, str(BIN))

import jarvo_tts_matcha as fon  # noqa: E402
import jarvo_tts_pl as pl  # noqa: E402
from jarvo_tts_pl import normalizuj as n  # noqa: E402


def _jarvo_tts():
    loader = importlib.machinery.SourceFileLoader("jarvo_tts", str(BIN / "jarvo-tts"))
    spec = importlib.util.spec_from_loader("jarvo_tts", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------ liczebniki

@pytest.mark.parametrize("liczba, slowa", [
    (0, "zero"), (7, "siedem"), (11, "jedenaście"), (21, "dwadzieścia jeden"), (100, "sto"), (215, "dwieście piętnaście"),
    (1000, "tysiąc"), (2026, "dwa tysiące dwadzieścia sześć"), (5000, "pięć tysięcy"), (12500, "dwanaście tysięcy pięćset"),
    (22000, "dwadzieścia dwa tysiące"), (1_000_000, "milion"), (3_400_000, "trzy miliony czterysta tysięcy"),
    (2_000_000_000, "dwa miliardy"),
])
def test_liczebnik_glowny(liczba, slowa):
    assert pl.liczebnik(liczba) == slowa


def test_liczebnik_dopelniacz_i_rodzaj():
    assert pl.liczebnik(5, dop=True) == "pięciu"
    assert pl.liczebnik(22, dop=True) == "dwudziestu dwóch"
    assert pl.liczebnik(2000, dop=True) == "dwóch tysięcy"
    assert pl.liczebnik(1000, dop=True) == "tysiąca"
    assert pl.liczebnik(1, rodzaj="z") == "jedna" and pl.liczebnik(1, rodzaj="n") == "jedno"
    assert pl.liczebnik(2, rodzaj="z") == "dwie" and pl.liczebnik(22, rodzaj="z") == "dwadzieścia dwie"
    assert pl.liczebnik(21, rodzaj="z") == "dwadzieścia jeden"               # „jeden” w złożonej liczbie bez odmiany


@pytest.mark.parametrize("liczba, forma, slowa", [
    (1, "m", "pierwszy"), (2, "d", "drugiego"), (3, "zm", "trzecia"), (3, "d", "trzeciego"), (11, "d", "jedenastego"),
    (15, "zd", "piętnastej"), (15, "zn", "piętnastą"), (21, "ms", "dwudziestym pierwszym"),
    (2026, "d", "dwa tysiące dwudziestego szóstego"), (2026, "ms", "dwa tysiące dwudziestym szóstym"),
    (1990, "d", "tysiąc dziewięćset dziewięćdziesiątego"), (1900, "d", "tysiąc dziewięćsetnego"),
    (2000, "d", "dwutysięcznego"), (2001, "m", "dwa tysiące pierwszy"),
])
def test_liczebnik_porzadkowy(liczba, forma, slowa):
    assert pl.porzadkowy(liczba, forma) == slowa


def test_odmiana_rzeczownika_po_liczbie():
    f = ("złoty", "złote", "złotych")
    assert [pl.odmiana(k, f) for k in (1, 2, 4, 5, 12, 14, 22, 25, 102)] == [
        "złoty", "złote", "złote", "złotych", "złotych", "złotych", "złote", "złotych", "złote"]


# ------------------------------------------------------------------ normalizator

@pytest.mark.parametrize("tekst, oczekiwany", [
    # daty i lata
    ("Dziś jest 11.10.2026.", "Dziś jest jedenastego października dwa tysiące dwudziestego szóstego roku."),
    ("Termin: 11.10.2026 r. Potem przerwa.",
     "Termin: jedenastego października dwa tysiące dwudziestego szóstego roku. Potem przerwa."),
    ("Raport z 2024-03-01.", "Raport z pierwszego marca dwa tysiące dwudziestego czwartego roku."),
    ("Od 1 stycznia 2027 r.", "Od pierwszego stycznia dwa tysiące dwudziestego siódmego roku."),
    ("W 2026 roku AI zmieni wszystko.", "W dwa tysiące dwudziestym szóstym roku ej aj zmieni wszystko."),
    ("Mieszkam tu od 2019 r.", "Mieszkam tu od dwa tysiące dziewiętnastego roku."),
    ("To był 1990 rok.", "To był tysiąc dziewięćset dziewięćdziesiąty rok."),
    ("W XXI w. wszystko przyspieszyło.", "W dwudziestym pierwszym wieku wszystko przyspieszyło."),
    # godziny
    ("Start o godz. 15:30.", "Start o godzinie piętnastej trzydzieści."),
    ("Spotkajmy się o 9:05 albo do 17:00.", "Spotkajmy się o dziewiątej zero pięć albo do siedemnastej."),
    ("Jest 12:45.", "Jest dwunasta czterdzieści pięć."),
    # kwoty, procenty, mnożniki, ułamki
    ("Koszt: 1 zł, 2 zł, 5 zł, 22 zł.", "Koszt: jeden złoty, dwa złote, pięć złotych, dwadzieścia dwa złote."),
    ("Budżet to 2,5 mln zł.", "Budżet to dwa i pół miliona złotych."),
    ("Zebraliśmy 1,5 tys. zł.", "Zebraliśmy półtora tysiąca złotych."),
    ("Przychód 12 500 zł i 3 tys. klientów.", "Przychód dwanaście tysięcy pięćset złotych i trzy tysiące klientów."),
    ("Wzrost o 42% w rok.", "Wzrost o czterdzieści dwa procent w rok."),
    ("Spadek o 0,75%.", "Spadek o zero przecinek siedemdziesiąt pięć procent."),
    ("Liczba pi to 3,14.", "Liczba pi to trzy przecinek czternaście."),
    ("Od 5 do 10 zł, ok. 20 osób.", "Od pięciu do dziesięciu złotych, około dwudziestu osób."),
    ("Trwa 10–15 minut.", "Trwa od dziesięciu do piętnastu minut."),
    ("Kosztuje $20 albo 15 €.", "Kosztuje dwadzieścia dolarów albo piętnaście euro."),
    ("Mamy 3.5 GB i -5°C.", "Mamy trzy i pół gigabajta i minus pięć stopni Celsjusza."),
    ("Jest 2x szybszy.", "Jest dwa razy szybszy."),
    ("Mamy 2 minuty, 2 godz. i 1 h.", "Mamy dwie minuty, dwie godziny i jedna godzina."),
    ("Było 1 000 000 widzów.", "Było milion widzów."),
    # telefony i kody
    ("Zadzwoń: +48 600 700 800.", "Zadzwoń: plus czterdzieści osiem sześćset siedemset osiemset."),
    ("Numer 600-700-800 albo 12 345 67 89.",
     "Numer sześćset siedemset osiemset albo dwanaście trzysta czterdzieści pięć sześćdziesiąt siedem osiemdziesiąt "
     "dziewięć."),
    ("Kod 007, tel. 600700800.", "Kod zero zero siedem, telefon sześćset siedemset osiemset."),
    # skróty
    ("Np. w poniedziałek, itd.", "Na przykład w poniedziałek, i tak dalej."),
    ("Zrobimy to itd. Potem reszta.", "Zrobimy to i tak dalej. Potem reszta."),
    ("Biuro przy ul. Długiej, pokój nr 12.", "Biuro przy ulicy Długiej, pokój numer dwanaście."),
    ("Ok. godz. 9 dzwoni dr Nowak.", "Około godziny dziewiątej dzwoni doktor Nowak."),
    ("Wg planu m.in. testy, tzn. sprawdzenie.", "Według planu między innymi testy, to znaczy sprawdzenie."),
    # skrótowce
    ("Raport w PDF wyślemy do HQ.", "Raport w pe de ef wyślemy do ha ku."),
    ("TTS i SEO to podstawa.", "te te es i es e o to podstawa."),
    ("Wyślij PDF-a.", "Wyślij pe de efa."),
    ("AI pomaga, OK?", "ej aj pomaga, okej?"),
    ("UWAGA NA STOPIEŃ PRZY WEJŚCIU", "uwaga na stopień przy wejściu"),
    ("Pisz na kontakt@jarvo.pl.", "Pisz na kontakt małpa jarvo kropka pe el."),
])
def test_normalizator(tekst, oczekiwany):
    assert n(tekst) == oczekiwany


def test_normalizator_zostawia_angielskie_wstawki_i_zwykly_tekst():
    assert n("Dzięki za {feedback}, wrzucę to na {Slack}a.") == "Dzięki za {feedback}, wrzucę to na {Slack}a."
    assert n("Po {PDF}ie 5 zł.") == "Po {PDF}ie pięć złotych."                # w klamrach bez zmian, poza nimi jak zwykle
    zwykly = "Zanim zaczniemy gotować, umyjmy ręce. Czy mam włączyć światło w kuchni?"
    assert n(zwykly) == zwykly
    assert not any(c.isdigit() for c in n("Mamy 7 dni, 24 h, 365 dni w roku i 1000 pomysłów."))


# ------------------------------------------------------------------ fonemizer: symbole i numery (bez espeak-ng)

def test_tablica_symboli_matcha_pl():
    assert len(fon.SYMBOLE) == 179 and fon.SYMBOLE[0] == "_" and fon.SYMBOLE[-1] == "̃"
    assert fon.SYMBOL_ID[" "] == 16 and fon.SYMBOL_ID["'"] == 176               # podwójny apostrof: ostatni, jak w Matcha
    assert fon.na_id("ab") == [0, fon.SYMBOL_ID["a"], 0, fon.SYMBOL_ID["b"], 0]
    assert fon.na_id("a☃b") == fon.na_id("ab")                                    # nieznany znak pominięty


def test_fonemy_z_espeak_jak_w_treningu():
    """Wzorce z symbols.js Space machinekind/matcha-tts-pl-v2 (port przeglądarkowy, „znak w znak” z treningiem)."""
    pytest.importorskip("phonemizer")
    pytest.importorskip("espeakng_loader")
    wzorce = {
        "Cześć, jestem robotem. Czy mogę ci w czymś pomóc?": "tʃˈɛɕtɕ, jˌɛstɛm rɔbˈɔtɛm. tʃɨ mˈɔɡɛ tɕi f tʃˈɨmɕ pˈɔmuts?",
        "Dr Nowak mówi: „to jest test” — naprawdę!": "dˈɔktɔr nˈɔvak mˈuvi: tɔ jɛst tˈɛst, naprˈavdɛ!",
        "Serio? To niesamowite!": "sˈɛrjɔ? tɔ ɲʲˌɛsamɔvˈitɛ!",
    }
    for tekst, ipa in wzorce.items():
        assert fon.fonemy(tekst) == ipa


# ------------------------------------------------------------------ jarvo-tts: głosy, zdania, akapity

def test_jarvo_tts_glosy_i_domyslny():
    t = _jarvo_tts()
    assert t.DOMYSLNY_GLOS == "pl-PL-Matcha-Meski"
    assert set(t.GLOSY) == {"pl-PL-Matcha-Meski", "pl-PL-Matcha-Damski", "en-US-Paradee"}
    assert {g["katalog"] for g in t.MATCHA_GLOSY.values()} == {"meski", "damski"}
    assert t.PAUZY_PL["zdanie"] == 0.33 and t.PAUZY_PL["akapit"] == 1.0             # jak PAUZY w film.py


def test_pauzy_lektora_jak_w_narracji_filmu():
    src = (REPO / "profiles" / "jarvo-wideo" / "scripts" / "film.py").read_text(encoding="utf-8")
    assert '"zdanie": 0.33' in src and '"akapit": 1.0' in src


def test_jarvo_tts_akapity_i_zdania_po_polsku():
    t = _jarvo_tts()
    tekst = "Spotkanie 11.10.2026 r. o godz. 15:30, np. w HQ. Potem przerwa.\n\nNowy akapit: dr Nowak mówi. Koniec!"
    assert t.podziel_akapity(tekst) == [
        ["Spotkanie 11.10.2026 r. o godz. 15:30, np. w HQ.", "Potem przerwa."],
        ["Nowy akapit: dr Nowak mówi.", "Koniec!"]]
    assert t.podziel_akapity(" \n\n ") == []


def test_jarvo_tts_dlugie_zdanie_w_kawalkach():
    t = _jarvo_tts()
    zdanie = ", ".join(["to jest dość długi fragment zdania"] * 30) + "."
    kawalki = t._kawalki_tekstu(zdanie, limit=120)
    assert all(len(k) <= 120 for k in kawalki) and len(kawalki) > 5
    assert " ".join(kawalki).replace(" ,", ",") == zdanie


def test_jarvo_tts_nieznany_glos_w_zadaniu(tmp_path):
    t = _jarvo_tts()
    plik = tmp_path / "z.json"
    plik.write_text(json.dumps([{"tekst": "Test.", "wyjscie": str(tmp_path / "a.wav"), "glos": "pl-PL-Nikt"}]),
                    encoding="utf-8")
    with pytest.raises(SystemExit):
        t.main(["--wsad", str(plik)])
    with pytest.raises(SystemExit):
        t.main(["Test.", "-o", str(tmp_path / "a.wav"), "--glos", "pl-PL-Nikt"])


def test_jarvo_tts_tekst_z_pliku_jak_woła_hermes(tmp_path, monkeypatch, capsys):
    """Głos floty: Hermes woła `jarvo-tts --plik {input_path} -o {output_path} --glos {voice}` (profiles/_host/config.yaml)."""
    t = _jarvo_tts()
    zlecone = []
    monkeypatch.setattr(t, "Modele", lambda: None)
    monkeypatch.setattr(t, "wykonaj", lambda modele, zadania: zlecone.extend(zadania) or [])
    plik = tmp_path / "input.txt"
    plik.write_text("-5 stopni? Dzień dobry.\n", encoding="utf-8")
    assert t.main(["--plik", str(plik), "-o", str(tmp_path / "a.wav"), "--glos", "pl-PL-Matcha-Damski"]) == 0
    assert zlecone == [{"tekst": "-5 stopni? Dzień dobry.", "wyjscie": str(tmp_path / "a.wav"), "szybkosc": 1.0,
                        "glos": "pl-PL-Matcha-Damski"}]
    (tmp_path / "pusty.txt").write_text("  \n", encoding="utf-8")
    with pytest.raises(SystemExit):
        t.main(["--plik", str(tmp_path / "pusty.txt"), "-o", str(tmp_path / "b.wav")])
    with pytest.raises(SystemExit):
        t.main(["Tekst.", "--plik", str(plik), "-o", str(tmp_path / "b.wav")])


def test_jarvo_tts_wynik_wsadu_ze_sciezka_przez_ukosnik(tmp_path, monkeypatch):
    """JSON wsadu podaje ścieżkę wyjścia z „/” na każdym systemie (jak inne ścieżki w JSON-ie floty)."""
    t = _jarvo_tts()

    class Model:
        rate = 22050

        def mow(self, tekst, szybkosc):
            return [0.0] * 2205, [(0.0, 0.1, tekst)]

    monkeypatch.setattr(t, "zapisz_wav", lambda sciezka, fala, rate: None)
    wynik = t.wykonaj({"pl-PL-Matcha-Meski": Model()}, [{"tekst": "Dzień dobry.", "wyjscie": str(tmp_path / "a.wav")}])
    assert wynik == [{"wyjscie": (tmp_path / "a.wav").as_posix(), "sekundy": 0.1, "zdania": [(0.0, 0.1, "Dzień dobry.")]}]


def test_jarvo_tts_wyjscie_w_utf8_takze_bez_trybu_utf8():
    """Pomoc (i JSON wsadu) w UTF-8 także bez PYTHONUTF8: na Windows potok dostaje wtedy stronę kodową ANSI."""
    env = {**os.environ, "PYTHONUTF8": "0"}
    env.pop("PYTHONIOENCODING", None)
    r = subprocess.run([sys.executable, str(BIN / "jarvo-tts"), "--help"], capture_output=True, env=env, timeout=60)
    assert r.returncode == 0
    pomoc = r.stdout.decode("utf-8")
    assert "Głosy:" in pomoc and "syntetyczny głos żeński" in pomoc


def test_jarvo_tts_katalogi_modeli_ze_srodowiska_jarva():
    """Natywnie modele lektora są w `<dane>/jarvo/models` (vendor/natywne.yaml: matcha-pl, paradee), a jarvo/srodowisko.py
    daje ich katalogi w JARVO_TTS_MATCHA_DIR i JARVO_TTS_MODEL_DIR: te same nazwy czyta jarvo-tts."""
    import jarvo.srodowisko as sr
    t = _jarvo_tts()
    src = (BIN / "jarvo-tts").read_text(encoding="utf-8")
    assert sr.MODELE["JARVO_TTS_MODEL_DIR"] == "paradee" and sr.MODELE["JARVO_TTS_MATCHA_DIR"] == "matcha-pl"
    assert 'os.environ.get("JARVO_TTS_MODEL_DIR"' in src and 'os.environ.get("JARVO_TTS_MATCHA_DIR"' in src
    lock = json.loads((REPO / "vendor" / "natywne.lock.json").read_text(encoding="utf-8"))["modele"]
    pliki = {p["cel"] for p in lock["matcha-pl"]["pliki"]}
    assert {f"{g['katalog']}/{t.MATCHA_ONNX}" for g in t.MATCHA_GLOSY.values()} <= pliki
    assert {f"{g['katalog']}/voices.json" for g in t.MATCHA_GLOSY.values()} <= pliki
    assert {"paradee_int8.onnx", "config.json"} <= {p["cel"] for p in lock["paradee"]["pliki"]}


# ------------------------------------------------------------------ jarvo-stt: modele z manifestu (V05, V10)

def _stt(monkeypatch, tmp_path):
    """jarvo-stt jako moduł, z katalogiem modeli w tmp_path."""
    loader = importlib.machinery.SourceFileLoader("jarvo_stt_modele", str(BIN / "jarvo-stt"))
    spec = importlib.util.spec_from_loader("jarvo_stt_modele", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    monkeypatch.setattr(mod, "MODELS_DIR", tmp_path / "models")
    return mod


def test_stt_modele_przypiete_w_manifescie(monkeypatch, tmp_path):
    """Parakeet i Silero mają w manifeście rewizję (pełny commit), adres z tą rewizją, sha256 i rozmiar każdego pliku,
    a pliki to te, których onnx-asr szuka w katalogu modelu (int8 encoder i decoder, vocab.txt, silero_vad.onnx)."""
    stt = _stt(monkeypatch, tmp_path)
    wpisy = stt.wpisy_modeli(REPO)
    assert set(wpisy) == set(stt.MODELE) == {"parakeet", "silero-vad"}
    for nazwa, w in wpisy.items():
        assert len(w["rewizja"]) == 40 and w["kiedy"] == "przy-uzyciu", nazwa
        for p in w["pliki"]:
            assert f"/resolve/{w['rewizja']}/" in p["url"] and p["url"].startswith("https://huggingface.co/"), p
            assert len(p["sha256"]) == 64 and int(p["rozmiar"]) > 0, p
    cele = {n: {p["cel"] for p in w["pliki"]} for n, w in wpisy.items()}
    assert {"encoder-model.int8.onnx", "decoder_joint-model.int8.onnx", "vocab.txt", "config.json"} <= cele["parakeet"]
    assert "silero_vad.onnx" in cele["silero-vad"] and stt.QUANT == "int8"


class _Serwer:
    """Pliki modeli z http://127.0.0.1 (pobieracz Jarva przyjmuje pętlę zwrotną tylko w testach)."""

    def __init__(self, pliki: dict[str, bytes]):
        import http.server
        import threading
        self.pliki, self.zapytania = pliki, []
        serwer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                serwer.zapytania.append(self.path)
                tresc = serwer.pliki.get(self.path)
                if tresc is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(tresc)))
                self.end_headers()
                self.wfile.write(tresc)

            def log_message(self, *a):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def zamknij(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def _repo_z_modelami(tmp_path: Path, url: str, tresci: dict[str, dict[str, bytes]], zla_suma: str = "") -> Path:
    """Kopia pakietu jarvo i manifest z małymi modelami (prawdziwe sumy treści, adresy z serwera testu)."""
    import hashlib
    import shutil
    repo = tmp_path / "repo"
    shutil.copytree(REPO / "jarvo", repo / "jarvo", ignore=shutil.ignore_patterns("__pycache__"))
    modele = {}
    for nazwa, pliki in tresci.items():
        modele[nazwa] = {"rewizja": "a" * 40, "kiedy": "przy-uzyciu", "katalog": f"kat-{nazwa}", "zrodlo": nazwa,
                         "licencja": "MIT", "pliki": [
                             {"cel": cel, "url": f"{url}/{nazwa}/{cel}", "rozmiar": len(b),
                              "sha256": "0" * 64 if cel == zla_suma else hashlib.sha256(b).hexdigest()}
                             for cel, b in pliki.items()]}
    (repo / "vendor").mkdir()
    (repo / "vendor" / "natywne.lock.json").write_text(json.dumps({"version": 1, "modele": modele}), encoding="utf-8")
    return repo


TRESCI = {"parakeet": {"config.json": b'{"model_type": "nemo-conformer-tdt"}', "vocab.txt": b"a 0\nb 1\n",
                       "encoder-model.int8.onnx": b"E" * 3000, "decoder_joint-model.int8.onnx": b"D" * 2000},
          "silero-vad": {"silero_vad.onnx": b"S" * 1500, "config.json": b"{}"}}


def test_stt_pobiera_modele_z_suma_przy_pierwszym_uzyciu(monkeypatch, tmp_path, capsys):
    """Pierwsze użycie: każdy plik z adresu manifestu, z sumą (pasek na stderr); znacznik i JARVO-ZRODLO.txt obok.
    Drugie: bez sieci (serwer już nie odpowiada). Zła suma: model się nie zapisuje, a jarvo-stt kończy się błędem."""
    import jarvo.modele  # noqa: F401  (pakiet jarvo z repo w sys.modules: jarvo-stt nie załaduje kopii z tmp_path)
    serwer = _Serwer({f"/{n}/{c}": b for n, pl in TRESCI.items() for c, b in pl.items()})
    stt = _stt(monkeypatch, tmp_path)
    monkeypatch.setenv("JARVO_REPO", str(_repo_z_modelami(tmp_path, serwer.url, TRESCI)))
    try:
        kat = stt.przygotuj_modele()
    finally:
        serwer.zamknij()
    assert kat == {"parakeet": tmp_path / "models" / "kat-parakeet", "silero-vad": tmp_path / "models" / "kat-silero-vad"}
    assert (kat["parakeet"] / "encoder-model.int8.onnx").read_bytes() == TRESCI["parakeet"]["encoder-model.int8.onnx"]
    assert (kat["parakeet"] / ".jarvo-model.json").is_file() and (kat["silero-vad"] / "JARVO-ZRODLO.txt").is_file()
    assert len(serwer.zapytania) == 6
    err = capsys.readouterr().err
    assert "pierwsze użycie, model parakeet" in err and "100%" in err
    assert stt.przygotuj_modele() == kat                          # serwer zamknięty: gotowe modele bez sieci
    assert len(serwer.zapytania) == 6

    serwer2 = _Serwer({f"/{n}/{c}": b for n, pl in TRESCI.items() for c, b in pl.items()})
    stt2 = _stt(monkeypatch, tmp_path / "drugi")
    monkeypatch.setattr(stt2, "LOCK", tmp_path / "jarvo-stt.lock")
    monkeypatch.setenv("JARVO_REPO", str(_repo_z_modelami(tmp_path / "drugi", serwer2.url, TRESCI, zla_suma="vocab.txt")))
    try:
        with pytest.raises(stt2.BrakModelu, match="suma sha256 się nie zgadza"):
            stt2.przygotuj_modele()
        nagranie = tmp_path / "nagranie_październik.wav"
        nagranie.write_bytes(b"RIFF")
        assert stt2.main([str(nagranie)]) == 1                      # bez modelu: kod 1 i komunikat, bez śladu
    finally:
        serwer2.zamknij()
    assert not (tmp_path / "drugi" / "models" / "kat-parakeet" / "vocab.txt").exists()
    assert "jarvo-stt: model parakeet się nie pobrał" in capsys.readouterr().err


def test_stt_bez_manifestu_niczego_nie_pobiera(monkeypatch, tmp_path):
    """Bez manifestu (JARVO_REPO, kod nad infra/bin, /opt/jarvo/repo) jarvo-stt nie schodzi do Hugging Face bez
    rewizji i sumy: BrakModelu, a main kończy się kodem 1."""
    stt = _stt(monkeypatch, tmp_path)
    monkeypatch.delenv("JARVO_REPO", raising=False)
    monkeypatch.setattr(stt, "__file__", str(tmp_path / "infra" / "bin" / "jarvo-stt"))
    monkeypatch.setattr(stt, "REPO_OBRAZU", str(tmp_path / "brak"))
    with pytest.raises(stt.BrakModelu, match="niczego nie pobiera"):
        stt.repo_jarva()
    monkeypatch.setenv("JARVO_REPO", str(REPO))
    assert stt.repo_jarva() == REPO


def test_stt_przenosi_pliki_z_dawnego_cache_hugging_face(monkeypatch, tmp_path):
    """Starszy jarvo-stt pobierał model przez huggingface_hub do <modele>/huggingface: blob LFS o sumie z manifestu
    trafia na miejsce bez pobierania, blob o innej treści zostaje pominięty."""
    import hashlib
    stt = _stt(monkeypatch, tmp_path)
    dobry, zly = b"model" * 100, b"inny" * 100
    s_dobry = hashlib.sha256(dobry).hexdigest()
    wpis = {"pliki": [{"cel": "encoder-model.int8.onnx", "sha256": s_dobry, "rozmiar": len(dobry),
                       "url": f"https://huggingface.co/istupakov/parakeet/resolve/{'b' * 40}/encoder-model.int8.onnx"},
                      {"cel": "vocab.txt", "sha256": "c" * 64, "rozmiar": len(zly),
                       "url": f"https://huggingface.co/istupakov/parakeet/resolve/{'b' * 40}/vocab.txt"}]}
    blobs = tmp_path / "models" / "huggingface" / "hub" / "models--istupakov--parakeet" / "blobs"
    blobs.mkdir(parents=True)
    (blobs / s_dobry).write_bytes(dobry)
    (blobs / ("c" * 64)).write_bytes(zly)
    kat = tmp_path / "models" / "parakeet"
    komunikaty = []
    assert stt.z_cache_hf(kat, wpis, lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(), komunikaty.append) == 1
    assert (kat / "encoder-model.int8.onnx").read_bytes() == dobry and not (kat / "vocab.txt").exists()
    assert komunikaty and "suma zgodna" in komunikaty[0]


def test_stt_laduje_modele_z_dysku_bez_huggingface(monkeypatch, tmp_path):
    """onnx-asr dostaje katalogi modeli (resolver bez sieci) i int8; HF_HUB_OFFLINE na wypadek innego wywołania."""
    import types
    stt = _stt(monkeypatch, tmp_path)
    wywolania = {}

    class Model:
        def with_vad(self, vad, max_speech_duration_s):
            wywolania["vad"] = (vad, max_speech_duration_s)
            return self

        def with_timestamps(self):
            return "gotowy"

    def load_model(model, path=None, **kw):
        wywolania["model"] = (model, path, kw.get("quantization"))
        return Model()

    def load_vad(model="silero", path=None, **kw):
        wywolania["silero"] = (model, path)
        return "vad"

    class Opcje:
        intra_op_num_threads = inter_op_num_threads = 0

    monkeypatch.setitem(sys.modules, "onnx_asr", types.SimpleNamespace(load_model=load_model, load_vad=load_vad))
    monkeypatch.setitem(sys.modules, "onnxruntime", types.SimpleNamespace(SessionOptions=Opcje))
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")            # stan sprzed testu wraca po nim (load ustawia „1”)
    monkeypatch.setenv("HF_HUB_DISABLE_TELEMETRY", "1")
    kat = {"parakeet": tmp_path / "p", "silero-vad": tmp_path / "s"}
    assert stt.load(kat) == "gotowy"
    assert wywolania["model"] == ("nemo-parakeet-tdt-0.6b-v3", str(tmp_path / "p"), "int8")
    assert wywolania["silero"] == ("silero", str(tmp_path / "s")) and wywolania["vad"] == ("vad", stt.MAX_SPEECH_S)
    assert os.environ["HF_HUB_OFFLINE"] == "1"
