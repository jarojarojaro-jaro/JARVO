"""jarvo/mozg_sesji.py: mózg sesji omp (ten sam silnik co skarbiec Jarva): przypomnienie przed turą (notatki, limit,
pomijane, pierwszeństwo, drugi ranking RRF), linki od właściciela w rejestrze (nowy, znany, ta sama treść pod innym
adresem X), sprawdzenie po turze (wyciąg odpowiedzi, przypomnienie, wiersz zastępczy znika), tożsamość (rdzeń mapy
w ZASADY, zapis tylko przy zmianie, notatka mapy), graf Mózgu, ocena, cały obieg w skrzynce z atrapą omp."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from jarvo import mozg_sesji as M

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "hq" / "plugin"))
import czytnik_omp  # noqa: E402
import mozg_zrodla  # noqa: E402


def notatka(katalog: Path, rel: str, tytul: str, streszczenie: str, tresc: str = "", typ: str = "fakt") -> Path:
    p = katalog / f"{rel}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntyp: {typ}\ntags: [x]\naktualizacja: 2026-11-20\nzrodlo: test\nstatus: aktualne\n---\n"
                 f"# {tytul}\n\n**{streszczenie}**\n\n{tresc}\n\n## Powiązane\n- [[index]]\n", encoding="utf-8")
    return p


@pytest.fixture
def wiki(tmp_path, monkeypatch):
    k = tmp_path / "wiki"
    notatka(k, "decyzje/2026-11-05-tylko-bezstratne", "2026-11-05: tylko optymalizacje bezstratne",
            "Właściciel: przyjmujemy tylko optymalizacje bezstratne (md5 i KLD zgodne).", typ="decyzja")
    notatka(k, "llm/inkling-2-mini", "Inkling 2 Mini: MoE z pętlą warstw",
            "Inkling 2 Mini na XTX: 33,9 t/s w Q3_K_XL, limit to kernele MoE, potencjał wyżej.")
    notatka(k, "lekcje/lekcja-vast-tylko-pelna-moc", "Lekcja: na Vaście tylko karty z pełną mocą",
            "Karta z mocą poniżej 85% fabrycznej idzie na czarną listę hosta.", typ="lekcja")
    notatka(k, "repo/strata", "Strata (Niko1221/Strata)", "Silnik bez ggml; delta wersji w ZRODLA.",
            "Wydanie v0.2.17 https://github.com/Niko1221/Strata/releases/tag/v0.2.17")
    notatka(k, "decyzje/_hub", "Decyzje", "", "lista wszystkich decyzji inkling vast strata bezstratne", typ="hub")
    (k / "log.md").write_text("# Dziennik\n\n## [2026-11-21] inkling vast strata bezstratne XTX MoE\n", encoding="utf-8")
    (k / "ZRODLA.md").write_text("---\ntyp: meta\n---\n# Rejestr źródeł\n\n**Jeden wiersz na źródło.**\n\n"
                                 "## Silniki\n\n| źródło | wersja / data | raport, notatka | werdykt | liczby | następnym razem |\n"
                                 "|---|---|---|---|---|---|\n| Project Maya v1.1.66 (https://x.com/PeasantSmith/status/2122753664456503314) "
                                 "| 11-17 | [[project-maya]] | nic dla 27B | – | – |\n\n## Powiązane\n- [[index]]\n",
                                 encoding="utf-8")
    monkeypatch.setattr(M, "stan_wektorow_instalacji", lambda: tmp_path / "brak-uslugi")
    return k


def cfg_z(tmp_path, wiki, **pola):
    d = {"katalog": str(wiki), "stan": str(tmp_path / "stan"), "pomin": ["log"], "pierwszenstwo": ["decyzje", "lekcje"],
         "zrodla": "ZRODLA.md", "notatek": 2, **pola}
    return M.Konfig.z_panelu(d, tmp_path / "skrzynka", "gpu")


def test_przypomnienie_notatki_limit_pomin_dziennik(tmp_path, wiki):
    cfg = cfg_z(tmp_path, wiki)
    b = M.przypomnienie(cfg, [{"tekst": "CO INKLING MIAŁ 50 T/S? to MoE, potencjał 250"}])
    assert b.startswith("<memory-context>\n## Wiedza: może się przydać") and b.endswith("</memory-context>")
    sciezki = M.notatki_bloku(b)
    assert sciezki[0] == "llm/inkling-2-mini"
    assert "log" not in sciezki and "decyzje/_hub" not in sciezki              # dziennik poza indeksem, hub bez streszczenia
    wpis = json.loads((tmp_path / "stan" / M.DZIENNIK).read_text().splitlines()[-1])
    assert wpis["notatki"] == sciezki and wpis["sesja"] == "gpu" and wpis["ms"] >= 0 and wpis["znakow"] == len(b)
    # ta sama notatka w następnej turze nie wraca (jest w historii rozmowy), w pomiarze tak
    assert "llm/inkling-2-mini" not in M.notatki_bloku(M.przypomnienie(cfg, [{"tekst": "inkling MoE t/s"}]))
    assert M.notatki_bloku(M.przypomnienie(cfg, [{"tekst": "inkling MoE t/s"}], zapisz=False))[0] == "llm/inkling-2-mini"


def test_limit_znakow_w_prompcie_i_pierwszenstwo(tmp_path, wiki):
    cfg = cfg_z(tmp_path, wiki, notatek=1, powtorka_tur=0)
    b = M.przypomnienie(cfg, [{"tekst": "inkling XTX t/s MoE vast moc bezstratne"}], zapisz=False)
    sciezki = M.notatki_bloku(b)
    assert sciezki[0] == "llm/inkling-2-mini" and len(sciezki) == 2            # 1 + jedna decyzja albo lekcja ponad limit
    assert sciezki[1].split("/")[0] in ("decyzje", "lekcje")
    cfg = cfg_z(tmp_path, wiki, w_prompcie=["llm/inkling-2-mini"], znakow=300, powtorka_tur=0)
    b = M.przypomnienie(cfg, [{"tekst": "inkling XTX t/s MoE"}], zapisz=False)
    assert "llm/inkling-2-mini" not in M.notatki_bloku(b)
    assert len(b.split("</memory-context>")[0]) <= 300 + len("<memory-context>\n") + 1


def test_drugi_ranking_rrf(tmp_path, wiki):
    skrypt = tmp_path / "ranking.py"
    skrypt.write_text("import json; print(json.dumps({'results': [{'path': 'wiki/repo/strata.md'}, "
                      "{'path': 'raporty/x.md'}]}))\n")
    cfg = cfg_z(tmp_path, wiki, ranking=[sys.executable, str(skrypt)], ranking_prefiks="wiki/", powtorka_tur=0)
    assert "repo/strata" in M.notatki_bloku(M.przypomnienie(cfg, [{"tekst": "zupełnie inne słowa"}], zapisz=False))


def test_klucz_linku():
    assert M.klucz_linku("https://x.com/HealthRanger/status/2123863744849580353?a=Rahe&s=52") == "status/2123863744849580353"
    assert M.klucz_linku("https://twitter.com/healthranger/status/2123863744849580353") == "status/2123863744849580353"
    assert M.klucz_linku("https://www.github.com/Niko1221/Strata/releases/tag/v0.2.18/") == \
        "github.com/niko1221/strata/releases/tag/v0.2.18"
    assert M.klucz_linku("https://youtube.com/watch?v=abc&t=3") == "youtube.com/watch?v=abc"


def test_linki_nowy_znany_i_obieg_po_turze(tmp_path, wiki):
    cfg = cfg_z(tmp_path, wiki)
    zrodla = wiki / "ZRODLA.md"
    m = {"tekst": "https://x.com/sensetime_ai/status/2122702684985938356?s=52 i "
                  "https://x.com/peasantsmith/status/2122753664456503314?a=x", "czas": "2026-11-17 18:09:55"}
    b = M.przypomnienie(cfg, [m])
    tekst = zrodla.read_text()
    assert M.SEKCJA_LINKOW in tekst and tekst.index(M.SEKCJA_LINKOW) < tekst.index("## Powiązane")
    assert "| https://x.com/sensetime_ai/status/2122702684985938356?s=52 (Telegram 2026-11-17) | 2026-11-17 | – | " \
           f"{M.CZEKA} |" in tekst
    assert tekst.count("2122753664456503314") == 1                              # znany pod innym zapisem: bez nowego wiersza
    assert "nowy, wiersz w `ZRODLA.md`" in b and "już w bazie, `ZRODLA.md:" in b
    # tura bez analizy: wyciąg odpowiedzi w werdykcie, link czeka i wraca w przypomnieniu
    r = M.sprawdz_linki(cfg, [m], "SenseNova-Loop-9B: pętla 32 → 56 warstw | sufit 2,1×.")
    assert r["czeka"] == ["status/2122702684985938356"]
    assert f"{M.BEZ_ANALIZY}; odpowiedź " in zrodla.read_text() and "SenseNova-Loop-9B: pętla 32 → 56 warstw / sufit" in \
        zrodla.read_text()
    b = M.przypomnienie(cfg, [{"tekst": "co z kartami?"}])
    assert "bez analizy w bazie" in b and "2122702684985938356" in b
    # model zapisał notatkę z adresem: wiersz zastępczy znika, link nie czeka
    notatka(wiki, "llm/sensenova-loop-9b", "SenseNova-Loop-9B", "Model z pętlą warstw.",
            "Źródło: https://x.com/SenseTime_AI/status/2122702684985938356")
    r = M.sprawdz_linki(cfg, [], "")
    assert r["gotowe"] == ["status/2122702684985938356"] and "?s=52 (Telegram" not in zrodla.read_text()
    assert json.loads((tmp_path / "stan" / M.CZEKAJACE).read_text()) == {}


def test_werdykt_od_modelu_konczy_czekanie_i_porzucenie(tmp_path, wiki):
    cfg = cfg_z(tmp_path, wiki)
    zrodla = wiki / "ZRODLA.md"
    m = {"tekst": "https://example.com/a?utm_source=x", "czas": "2026-11-22 10:00:00", "zrodlo": "panel"}
    M.przypomnienie(cfg, [m])
    assert "(panel 2026-11-22)" in zrodla.read_text()
    zrodla.write_text(zrodla.read_text().replace(f"| {M.CZEKA} |", "| Nic dla nas: blog bez liczb. |"))
    assert M.sprawdz_linki(cfg, [m], "x")["gotowe"] == ["example.com/a"]
    m2 = {"tekst": "https://example.org/b", "czas": "2026-11-22 10:00:00"}
    M.przypomnienie(cfg, [m2])
    M.sprawdz_linki(cfg, [m2], "odpowiedź")
    for _ in range(M.POWTORZEN_LINKU):
        assert "example.org/b" in M.przypomnienie(cfg, [{"tekst": "dalej"}])
    assert M.sprawdz_linki(cfg, [], "")["porzucone"] == ["example.org/b"]
    assert "example.org/b" not in M.przypomnienie(cfg, [{"tekst": "dalej"}])


def test_dopisek_bez_zapisu_rejestru_a_po_turze_tak(tmp_path, wiki):
    cfg = cfg_z(tmp_path, wiki)
    m = {"tekst": "https://example.net/c", "czas": "2026-11-22 11:00:00"}
    b = M.przypomnienie(cfg, [m], rejestruj=False)
    assert "example.net/c: nowy" in b and "example.net/c" not in (wiki / "ZRODLA.md").read_text()
    M.sprawdz_linki(cfg, [m], "Odpowiedź o c.")
    assert "https://example.net/c (Telegram 2026-11-22)" in (wiki / "ZRODLA.md").read_text()


def test_zwiad_bez_rejestru(tmp_path, wiki):
    cfg = cfg_z(tmp_path, wiki)
    M.przypomnienie(cfg, [{"tekst": "raport https://github.com/a/b", "zrodlo": "zwiad"}])
    assert "github.com/a/b" not in (wiki / "ZRODLA.md").read_text()


def test_tresc_linku_w_zapytaniu():
    surowy = json.dumps({"linki": [{"url": "u", "tekst": "Run Inkling 2 Mini, the strongest 26.4B model"}]})
    assert "Inkling 2 Mini" in M.tekst_zapytania([{"tekst": "a co z tym?"}], [surowy])
    assert "Inkling" in M.tekst_zapytania([{"tekst": ""}], [surowy[:60]])        # ucięty JSON: pola po kolei


class Wpis:
    def __init__(self, tmp_path, wiki, **t):
        self.klucz, self.skrzynka = "gpu", tmp_path / "skrzynka"
        self.wiedza = {"katalog": str(wiki), "stan": str(tmp_path / "stan")}
        self.tozsamosc = t


def test_tozsamosc_rdzen_zapis_przy_zmianie_i_notatka(tmp_path, wiki):
    t = tmp_path / "toz"
    t.mkdir()
    (t / "SOUL.md").write_text("# Kim jestem\nKernel.\n")
    (t / "ZASADY.md").write_text("# Zasady\n- bezstratnie\n\n<!-- Jarvo:MAPA -->\n\n## Koniec\n")
    (t / "MAPA.md").write_text("## Kim jestem\n<!-- Jarvo:RDZEN -->\n- Kernel, sesja omp.\n<!-- /Jarvo:RDZEN -->\n"
                               "Szczegół tylko w notatce.\n\n## Gdzie co jest\n<!-- Jarvo:RDZEN -->\n- wiki: ~/dev/KERNEL/wiki\n"
                               "<!-- /Jarvo:RDZEN -->\n")
    (t / "arsenal.md").write_text("# A\n\n## Zasoby\n- InstaBox: CPU\n\n## Inne\n- nie\n")
    w = Wpis(tmp_path, wiki, soul=str(t / "SOUL.md"), zasady=str(t / "ZASADY.md"), mapa=str(t / "MAPA.md"),
             plik=str(tmp_path / "system.md"), arsenal=str(t / "arsenal.md"), notatka="kernel-od-a-do-z.md",
             tytul="Kernel od A do Z")
    p = M.tozsamosc(w)
    s = p.read_text()
    assert s.startswith("# Kim jestem\nKernel.") and "### Kim jestem\n- Kernel, sesja omp." in s
    assert "Szczegół tylko w notatce" not in s and "<!-- Jarvo" not in s and "## Koniec" in s
    assert "# Arsenał floty" in s and "- InstaBox: CPU" in s and "- nie" not in s
    n = (wiki / "kernel-od-a-do-z.md").read_text()
    assert n.startswith("---\ntyp: meta") and "# Kernel od A do Z" in n and "Szczegół tylko w notatce" in n
    mtime = p.stat().st_mtime_ns
    M.tozsamosc(w)
    assert p.stat().st_mtime_ns == mtime                                        # ta sama treść: ten sam plik (cache, proces)
    # sekcje mapy wracają w przypomnieniu (szczegóły poza promptem)
    b = M.przypomnienie(M.konfig(w), [{"tekst": "gdzie jest wiki i szczegół"}], zapisz=False)
    assert any(s.startswith("kernel-od-a-do-z") for s in M.notatki_bloku(b))


def test_graf_mozgu_i_ocena(tmp_path, wiki):
    cfg = cfg_z(tmp_path, wiki, graf=str(tmp_path / "graf.json"), powtorka_tur=0)
    r = M.odswiez_po_turze(cfg)
    assert r["graf"] is True and M.odswiez_po_turze(cfg)["graf"] is False
    g = mozg_zrodla.normalizuj(json.loads((tmp_path / "graf.json").read_text()))
    wezly = {w["id"]: w for w in g["wezly"]}
    assert wezly["decyzje/_hub"]["hub"] is True and "log" not in wezly
    assert wezly["llm/inkling-2-mini"]["opis"].startswith("Inkling 2 Mini na XTX")
    o = M.ocena(cfg, [{"pytanie": "inkling MoE XTX", "wzor": ["llm/inkling-2-mini.md"]},
                      {"pytanie": "zupełnie nic", "wzor": ["repo/strata"]}])
    assert o["pytan"] == 2 and o["trafione"] == 1 and o["hit_at_k"] == 0.5 and o["mrr"] == 0.5


def test_blok_przed_naglowkiem_nie_trafia_do_dymku():
    tekst = ("Wiadomości od właściciela (telegram). Zrób je.\n\n<memory-context>\n## Wiedza: może się przydać\n"
             "- `llm/x` · X: y\n</memory-context>\n\n[Telegram · gpu · 2026-11-22 10:00:00 · wiadomość 1/1]\nlink")
    assert czytnik_omp.bloki_obwiedni(tekst) == [{"zrodlo": "telegram", "tekst": "link", "klucz": None}]
