"""Księga błędów (docs/WIEDZA.md §4b): notatki `bledy/` z sygnaturami, zasiew z repo, lint, kompilacja szkicu `blad`
i dopisek pod wynikiem narzędzia (wiedza/plugin/ksiega_bledow.py, hak `transform_tool_result`)."""
import contextlib
import importlib.util
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "wiedza"))
import wiedza as w  # noqa: E402
import kompilacja as k  # noqa: E402

_spec = importlib.util.spec_from_file_location("jarvo_ksiega_bledow_test", REPO / "wiedza" / "plugin" / "ksiega_bledow.py")
kb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kb)

ZASIEW = REPO / "wiedza" / "bledy"
TURNSTILE = "bledy/cloudflare nie przepuszcza komputera, krok na telefonie floty"
GOOGLE = "bledy/google nie loguje w przeglądarce komputera, konta google na telefonie"
EKRAN = "bledy/ekran komputera zajęty przez inną kartę"
FLEET = {"orchestrator": "jarvo", "agents": [
    {"name": "jarvo-web", "short": "Web", "title": "Web Senior Dev", "emoji": "🌐", "kind": "specialist", "description": "Strony i SEO.",
     "room": "devlab", "label": "Pracownia", "telegram_topic": "web", "autonomy_max": "A1", "skills": [], "scripts": []}]}


@contextlib.contextmanager
def _bez_zamka(_plik, _czekaj=0):
    yield True


@pytest.fixture
def sk(tmp_path, monkeypatch):
    """Skarbiec po zasiewie jak przy instalacji: flota, SCHEMA i księga błędów z repo."""
    monkeypatch.setenv("WIEDZA_DZIS", "2026-11-17")
    monkeypatch.setattr(k, "ROWNOLEGLE", 1)
    kb._ksiegi.clear()
    kb._sesje.clear()
    fleet = tmp_path / "fleet.json"
    fleet.write_text(json.dumps(FLEET, ensure_ascii=False), encoding="utf-8")
    root, stan = tmp_path / "knowledge", tmp_path / "state"
    assert w.main(["--skarbiec", str(root), "--stan", str(stan), "zasiej", "--fleet", str(fleet), "--bledy", str(ZASIEW)]) == 0
    return w.Skarbiec(root, stan)


def dopisek(sk, narzedzie, wynik, status="ok", sesja="s1"):
    return kb.dopisek(w, narzedzie, wynik, status, sesja, sk.root, sk.stan, zamek=_bez_zamka, zamien=os.replace)


# ------------------------------------------------------------------------------------------------ zasiew i lint

def test_zasiew_ksiegi_jest_idempotentny_i_nie_nadpisuje(sk):
    pliki = sorted(p.stem for p in ZASIEW.glob("*.md"))
    assert len(pliki) >= 12 and all(sk.istnieje(f"bledy/{p}") for p in pliki)
    assert sk.istnieje("bledy/_hub-bledy")
    assert w.zasiej_bledy(sk, ZASIEW) == 0                                    # drugi zasiew: nic nowego
    # notatka zmieniona w skarbcu (kompilacja dopisała przypadek) zostaje; usunięta nie wraca przy następnym wdrożeniu
    zmieniona = sk.plik(TURNSTILE)
    zmieniona.write_text(zmieniona.read_text(encoding="utf-8").replace("wystapienia: 1", "wystapienia: 7"), encoding="utf-8")
    sk.plik(GOOGLE).unlink()
    assert w.zasiej_bledy(sk, ZASIEW) == 0
    assert "wystapienia: 7" in zmieniona.read_text(encoding="utf-8") and not sk.istnieje(GOOGLE)
    # świeży stan (nowa instalacja na starym skarbcu): istniejącej notatki nie nadpisuje
    (sk.stan / w.ZASIANE_BLEDY).unlink()
    assert w.zasiej_bledy(sk, ZASIEW) == 1 and "wystapienia: 7" in zmieniona.read_text(encoding="utf-8")


def test_zasiew_wymienia_nietknieta_notatke_na_nowsza_wersje(sk, tmp_path):
    """18.11 notatka o zajętym ekranie dostała sygnatury z tekstu odmowy Komputera; skarbiec zasiany 17.11 (state
    z samą listą) ma dostać nową wersję, ale notatki zmienionej przez kompilację zasiew nie rusza."""
    repo = tmp_path / "repo-bledy"
    shutil.copytree(ZASIEW, repo)
    stan = sk.stan / w.ZASIANE_BLEDY
    stan.write_text(json.dumps(sorted(json.loads(stan.read_text(encoding="utf-8")))), encoding="utf-8")   # format 17.11
    stara = sk.plik(EKRAN)                              # zasiew 17.11: notatka bez zmian po utworzeniu
    fm = stara.read_text(encoding="utf-8")
    utw = fm.split("utworzono: ", 1)[1][:10]
    stara.write_text(re.sub(r"zmieniono: \S+", f"zmieniono: {utw}", fm, count=1), encoding="utf-8")
    ekran, google = (repo / f"{r.split('/', 1)[1]}.md" for r in (EKRAN, GOOGLE))
    ekran.write_text(ekran.read_text(encoding="utf-8").replace("ekran_zmieniony,", "ekran_zmieniony, nowa sygnatura,"),
                     encoding="utf-8")
    google.write_text(google.read_text(encoding="utf-8").replace("wystapienia: 1", "wystapienia: 1\nkarta: t_9"),
                      encoding="utf-8")
    zmieniona = sk.plik(GOOGLE)                         # kompilacja dopisała przypadek: inna data i źródło
    zmieniona.write_text(zmieniona.read_text(encoding="utf-8").replace("zmieniono: 2026-11-17", "zmieniono: 2026-11-18"),
                         encoding="utf-8")
    assert w.zasiej_bledy(sk, repo) == 1
    assert "nowa sygnatura" in sk.plik(EKRAN).read_text(encoding="utf-8")
    assert "karta: t_9" not in zmieniona.read_text(encoding="utf-8")
    zapis = json.loads(stan.read_text(encoding="utf-8"))
    assert isinstance(zapis, dict) and len(zapis[EKRAN]) == 64
    assert w.zasiej_bledy(sk, repo) == 0                # drugi raz bez zmian
    ekran.write_text(ekran.read_text(encoding="utf-8").replace("nowa sygnatura", "trzecia sygnatura"), encoding="utf-8")
    assert w.zasiej_bledy(sk, repo) == 1 and "trzecia sygnatura" in sk.plik(EKRAN).read_text(encoding="utf-8")


def test_lint_przyjmuje_ksiege_i_lapie_zle_sygnatury(sk):
    ix = w.Indeks(sk)
    try:
        r = w.lint(sk, ix)
        assert r["bledy"] == []
        assert [o for o in r["ostrzezenia"] if "bledy/" in o] == []          # zasiew: linki, sygnatury, krok, typ
        hub = sk.plik("bledy/_hub-bledy").read_text(encoding="utf-8")
        assert f"[[{TURNSTILE}|" in hub and "wystąpień: 1" in hub
        sk.zapisz_plik("bledy/zly blad", w.sklej(
            {"typ": "lekcja", "tagi": ["x"], "utworzono": "2026-11-17", "zmieniono": "2026-11-17", "status": "aktualna",
             "zrodlo": "test", "sygnatury": ["/(niedomkniety/"], "wystapienia": "dwa"},
            f"# Zły błąd\n\n**Bez kroku.**\n\nObjaw: coś.\n\n## Powiązane\n- hub: [[bledy/_hub-bledy]]\n- [[{TURNSTILE}]]\n"))
        r = w.lint(sk, ix)
        assert any("błędne wyrażenie w sygnaturze `/(niedomkniety/`" in b for b in r["bledy"])
        assert any("`wystapienia: dwa` nie jest liczbą" in b for b in r["bledy"])
        ostrz = " | ".join(r["ostrzezenia"])
        assert "bez akapitu „Jak poprawnie:”" in ostrz and "typ `lekcja` zamiast `blad`" in ostrz
    finally:
        ix.zamknij()


def test_lista_frontmatteru_z_przecinkiem_w_cudzyslowie():
    fm, _ = w.podziel('---\nsygnatury: [a, "b, c", \'d\', "/x{1,2}\\\\d/"]\n---\n# T\n')
    assert fm["sygnatury"] == ["a", "b, c", "d", "/x{1,2}\\d/"]
    tekst = w.sklej({"sygnatury": ["We couldn't verify you're human", "x, y", "/a\\b/"]}, "# T\n")
    assert w.podziel(tekst)[0]["sygnatury"] == ["We couldn't verify you're human", "x, y", "/a\\b/"]
    assert w.zly_naglowek(tekst) == ""


def test_wpisy_ksiegi_krok_jak_poprawnie(sk):
    wpisy = {e["sciezka"]: e for e in w.wpisy_ksiegi(sk)}
    t = wpisy[TURNSTILE]
    assert t["jak"].startswith("w Komputerze najwyżej jedna próba") and "MCP `phone`" in t["jak"] and "**" not in t["jak"]
    assert t["wystapienia"] == 1 and t["narzedzia"] == []
    assert wpisy["bledy/ekran komputera zajęty przez inną kartę"]["narzedzia"] == ["komputer", "computer_use"]


# ------------------------------------------------------------------------------------------------ dopisek pod wynikiem

def test_odmowa_turnstile_dostaje_lekcje_raz_na_sesje_i_licznik(sk):
    wynik = json.dumps({"status": "zablokowane", "rule": "weryfikacja_czlowieka",
                        "reason": "okienko „jestem człowiekiem” na dataannotation.tech: Weryfikacja negatywna"})
    d = dopisek(sk, "komputer", wynik)
    assert d.startswith("\n\n[księga błędów] To już było: Cloudflare nie przepuszcza Komputera")
    assert "jak poprawnie: w Komputerze najwyżej jedna próba" in d and f'wiedza_czytaj("{TURNSTILE}")' in d
    assert "(wystąpień: 2)" in d                                              # 1 z notatki + to przypomnienie
    licznik = w.licznik_bledow(sk.stan)
    assert licznik[TURNSTILE]["przypomnien"] == 1
    # ta sama sesja: jedna linia, licznik bez zmian; nowa sesja: pełny blok i licznik +1
    d2 = dopisek(sk, "komputer", wynik)
    assert "masz wyżej w tej rozmowie" in d2 and "jak poprawnie:" not in d2
    assert w.licznik_bledow(sk.stan)[TURNSTILE]["przypomnien"] == 1
    assert "(wystąpień: 3)" in dopisek(sk, "mcp__phone__act", "We couldn’t verify you’re human", sesja="s2")
    assert w.licznik_bledow(sk.stan)[TURNSTILE]["przypomnien"] == 2


def test_sukces_bez_dopisku_a_czytanie_tresci_nie_przypomina(sk):
    assert dopisek(sk, "komputer", '{"status": "ok", "url": "https://example.com"}') == ""
    assert dopisek(sk, "web_search", "Wyniki: 3 strony o kawie") == ""
    # sygnatura w treści pliku albo notatki to nie stan narzędzia
    assert dopisek(sk, "read_file", "notatka: We couldn't verify you're human") == ""
    assert dopisek(sk, "wiedza_czytaj", "We couldn't verify you're human", status="error") == ""
    # notatka z polem `narzedzia`: kod odmowy `zajete` tylko w wyniku Komputera; „zajęte” z ogonkiem to nie kod
    assert dopisek(sk, "browser_navigate", '{"odmowa": "zajete"}') == ""
    assert "Ekran Komputera zajęty" in dopisek(sk, "komputer", '{"odmowa": "zajete", "powod": "ekran ma karta t_1"}')
    assert dopisek(sk, "komputer", "Wszystkie miejsca zajęte", sesja="s3") == ""


def test_blad_bez_notatki_prosi_o_zapis_raz(sk):
    d = dopisek(sk, "terminal", '{"error": "ModuleNotFoundError: No module named foo"}', status="error")
    assert "Tego błędu nie ma w księdze" in d and "wiedza_zapisz z typ=blad" in d
    assert dopisek(sk, "terminal", '{"error": "inny błąd"}', status="error") == ""        # raz na sesję i narzędzie
    assert "Tego błędu nie ma" in dopisek(sk, "terminal", '{"error": "x"}', status="error", sesja="s9")
    assert dopisek(sk, "terminal", '{"output": "ok"}', status="ok", sesja="s10") == ""


def test_najwyzej_dwie_notatki_i_ograniczona_dlugosc(sk):
    dlugi = ("x" * 200_000 + " We couldn't verify you're human · This browser or app may not be secure · "
             "API rate limit exceeded · Iteration budget exhausted")
    d = dopisek(sk, "browser_navigate", dlugi, status="error")
    assert d.count("To już było:") == kb.MAX_TRAFIEN
    assert len(d) <= kb.MAX_ZNAKOW_BLOKU + len(kb.NAGLOWEK) + kb.MAX_TRAFIEN


def test_wynik_json_z_ucieczkami_unicode(sk):
    wynik = json.dumps({"error": "Ta przeglądarka lub aplikacja może nie być bezpieczna"})       # ensure_ascii: \u0105
    assert "\\u0105" in wynik
    assert "Google nie loguje w przeglądarce Komputera" in dopisek(sk, "komputer", wynik, status="error")


def test_nowa_notatka_w_ksiedze_widoczna_bez_restartu(sk, monkeypatch):
    monkeypatch.setattr(kb, "KONTROLA_S", 0.0)
    assert dopisek(sk, "browser_navigate", "ERR_SSL_PROTOCOL_ERROR") == ""
    sk.zapisz_plik("bledy/certyfikat strony nieważny", w.sklej(
        {"typ": "blad", "tagi": ["x"], "utworzono": "2026-11-17", "zmieniono": "2026-11-17", "status": "aktualna",
         "zrodlo": "test", "sygnatury": ["ERR_SSL_PROTOCOL_ERROR"], "wystapienia": 1},
        "# Certyfikat strony nieważny\n\n**Strona bez ważnego certyfikatu.**\n\nObjaw: błąd SSL.\n\n"
        "Jak poprawnie: sprawdź adres http i zgłoś właścicielowi strony.\n"))
    time.sleep(0.01)
    assert "Certyfikat strony nieważny" in dopisek(sk, "browser_navigate", "net::ERR_SSL_PROTOCOL_ERROR")


# ------------------------------------------------------------------------------------------------ szkic i kompilacja

TRESC_BLEDU = ("Objaw: przy pobraniu paczki npm wynik „EINTEGRITY sha512 mismatch”.\n\n"
               "Przyczyna: uszkodzony cache npm po przerwanym pobraniu.\n\n"
               "Jak poprawnie: `npm cache verify`, potem jedno ponowienie instalacji; drugi raz ten sam błąd = zgłoś.")


def test_szkic_bledu_wymaga_sygnatur_i_kroku(sk):
    with pytest.raises(ValueError, match="sygnatury"):
        w.zapisz_szkic(sk, "blad", "Npm EINTEGRITY", TRESC_BLEDU, "karta t_1", "jarvo-web")
    with pytest.raises(ValueError, match="Jak poprawnie"):
        w.zapisz_szkic(sk, "blad", "Npm EINTEGRITY", "Objaw: coś.", "karta t_1", "jarvo-web", sygnatury_bledu=["EINTEGRITY"])
    with pytest.raises(ValueError, match="błędne wyrażenie"):
        w.zapisz_szkic(sk, "blad", "Npm EINTEGRITY", TRESC_BLEDU, "karta t_1", "jarvo-web", sygnatury_bledu=["/(x/"])
    with pytest.raises(ValueError, match="tylko szkic błędu"):
        w.zapisz_szkic(sk, "fakt", "Fakt", "Treść.", "karta t_1", "jarvo-web", sygnatury_bledu=["x"])
    rel = w.zapisz_szkic(sk, "blad", "Npm EINTEGRITY", TRESC_BLEDU, "karta t_1", "jarvo-web",
                         sygnatury_bledu=["EINTEGRITY", "sha512 mismatch, cache"])
    assert w.podziel(sk.plik(rel).read_text(encoding="utf-8"))[0]["sygnatury"] == ["EINTEGRITY", "sha512 mismatch, cache"]


def _model(odpowiedzi):
    kolejka = list(odpowiedzi)
    return lambda system, user: json.dumps(kolejka.pop(0) if kolejka else {"wyniki": []}, ensure_ascii=False)


def test_kompilacja_kladzie_blad_w_ksiedze_i_liczy_wystapienia(sk):
    w.zapisz_szkic(sk, "blad", "Npm EINTEGRITY", TRESC_BLEDU, "karta t_1", "jarvo-web", sygnatury_bledu=["EINTEGRITY"])
    # model daje folder pojęć i typ lekcji: szkic błędu i tak trafia do księgi jako `blad`
    r = k.Kompilacja(sk, _model([{"wyniki": [{
        "decyzja": "nowa", "sciezka": "pojecia/npm eintegrity", "typ": "lekcja", "tytul": "Npm EINTEGRITY",
        "streszczenie": "Uszkodzony cache npm daje EINTEGRITY", "tresc": TRESC_BLEDU, "sygnatury": ["sha512 mismatch"],
        "linki": [TURNSTILE], "powod": "nowy błąd"}]}])).uruchom()
    assert r["nowe"] == 1 and sk.istnieje("bledy/npm eintegrity") and not sk.istnieje("pojecia/npm eintegrity")
    fm = sk.wczytaj("bledy/npm eintegrity").fm
    assert fm["typ"] == "blad" and fm["sygnatury"] == ["EINTEGRITY", "sha512 mismatch"] and fm["wystapienia"] == "1"
    # ten sam błąd zgłoszony znowu: aktualizacja notatki w księdze, wystąpienia +1, sygnatury scalone
    time.sleep(0.01)
    w.zapisz_szkic(sk, "blad", "Npm EINTEGRITY znowu", TRESC_BLEDU + " Drugi przypadek 17.11.", "karta t_2", "jarvo-web",
                   sygnatury_bledu=["npm ERR! code EINTEGRITY"])
    r = k.Kompilacja(sk, _model([{"wyniki": [{
        "decyzja": "aktualizacja", "sciezka": "bledy/npm eintegrity", "typ": "blad", "tytul": "Npm EINTEGRITY",
        "streszczenie": "Uszkodzony cache npm daje EINTEGRITY", "tresc": TRESC_BLEDU + " Drugi przypadek 17.11.",
        "powod": "ten sam błąd"}]}])).uruchom()
    assert r["aktualizacje"] == 1
    fm = sk.wczytaj("bledy/npm eintegrity").fm
    assert fm["wystapienia"] == "2" and fm["sygnatury"] == ["EINTEGRITY", "sha512 mismatch", "npm ERR! code EINTEGRITY"]
    assert fm["zrodlo"] == "karta t_1; karta t_2"
    # i od razu działa pod wynikiem narzędzia
    kb._ksiegi.clear()
    assert "Npm EINTEGRITY" in dopisek(sk, "terminal", '{"error": "npm ERR! code EINTEGRITY"}', status="error", sesja="s5")
