"""Biblioteka dźwięków CC0 (scripts/dzwieki.py → hq/web/dzwieki) i menu Audio: ten sam katalog i te same pliki
w edytorze HQ (plugin_api: /edit/dzwieki, /edit/dzwiek, /edit/wyodrebnij, /edit/lektor, /edit/nagranie)
i u Wideografa (projekt.py dzwieki, dodaj-dzwiek, wyodrebnij, lektor). Dodanie kopiuje plik obok filmu."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dz = _load("scripts/dzwieki.py", "jarvo_dzwieki_test")
pr = _load("profiles/jarvo-wideo/scripts/projekt.py", "jarvo_projekt_dzwieki_test")
ed = pr.ed
LIB = ROOT / "hq" / "web" / "dzwieki"
HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def test_biblioteka_zgodna_z_lista():
    # pliki, sumy, katalog i LICENCJE.md zgadzają się z DZWIEKI (bez sieci i ffmpeg)
    assert dz.bledy() == []
    kat = ed.dzwieki_katalog(LIB)
    assert [k["id"] for k in kat["kategorie"]] == [k for k, *_ in dz.KATEGORIE]
    assert len(kat["dzwieki"]) == len(dz.DZWIEKI)
    for k, *_ in dz.KATEGORIE:                       # każda kategoria ma czym wybierać
        assert sum(d["kat"] == k for d in kat["dzwieki"]) >= 5, k
    assert all(d["licencja"] == "CC0-1.0" and d["autor"] and d["zrodlo"].startswith("https://") for d in kat["dzwieki"])
    # rozmiar w ryzach (repo i obraz): efekty krótkie, podkłady najwyżej minuta
    assert sum(p.stat().st_size for p in LIB.glob("*/*.mp3")) < 12 * 2**20
    assert all(d["dl"] <= (60.1 if d["kat"] == "muzyka" else 10.1) for d in kat["dzwieki"])


def test_tylko_cc0_z_freesound():
    strona = f'<a href="http://{dz.CC0}/">CC0</a> data-mp3="https://cdn.freesound.org/previews/60/60013_71257-lq.mp3"'
    assert dz.podglad_fs(strona, 60013) == "https://cdn.freesound.org/previews/60/60013_71257-hq.mp3"
    with pytest.raises(SystemExit, match="CC0"):
        dz.podglad_fs(strona.replace(dz.CC0, "creativecommons.org/licenses/by/4.0"), 60013)


def test_dodanie_kopiuje_plik_obok_filmu(tmp_path):
    film = tmp_path / "film.mp4"
    film.write_bytes(b"x")
    dest = ed.dzwiek_do_filmu(LIB, "whoosh", film)
    assert dest == tmp_path / "dzwieki" / "whoosh.mp3" and dest.read_bytes() == (LIB / "przejscia" / "whoosh.mp3").read_bytes()
    assert ed.dzwiek_do_filmu(LIB, "whoosh", film) == dest        # drugi raz ta sama kopia
    with pytest.raises(ed.ProjectError):
        ed.dzwiek_do_filmu(LIB, "nie-ma-takiego", film)
    assert ed.dzwiek_plik(None, "whoosh") is None


def test_katalog_nie_wychodzi_poza_biblioteke(tmp_path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "tajne.mp3").write_bytes(b"x")
    (tmp_path / "lib" / "katalog.json").write_text(json.dumps({"dzwieki": [{"id": "zly", "plik": "../tajne.mp3"}]}))
    assert ed.dzwiek_plik(tmp_path / "lib", "zly") is None


def test_sciezki_i_polecenia_audio(tmp_path):
    film = tmp_path / "f" / "film.mp4"
    assert ed.wyodrebnij_cel(film, Path("/x/Mój film (1).mov")) == tmp_path / "f" / "dzwieki" / "Mój-film-1-dzwiek.m4a"
    assert "copy" in ed.wyodrebnij_cmd(Path("a.mp4"), Path("b.m4a"), "aac")
    assert "192k" in ed.wyodrebnij_cmd(Path("a.mp4"), Path("b.m4a"), "opus")
    a = ed.lektor_cel(film, "Cześć, to test!", "pl-PL-MarekNeural", "+0%")
    assert a.parent == tmp_path / "f" / "lektor" and a.name.startswith("lektor-cześć-to-test-")
    assert a == ed.lektor_cel(film, "Cześć, to test!", "pl-PL-MarekNeural", "+0%")      # ten sam tekst = ten sam plik
    assert a != ed.lektor_cel(film, "Cześć, to test!", "pl-PL-ZofiaNeural", "+0%")
    assert [ed.tempo_tts(v) for v in (10, "-5%", "+80", "x", None)] == ["+10%", "-5%", "+50%", "+0%", "+0%"]
    assert ed.nagranie_cel(film, 0).suffix == ".m4a" and "aac" in ed.nagranie_cmd(Path("a.webm"), Path("b.m4a"))


def test_lista_dla_agenta(capsys):
    assert pr.main(["dzwieki", "--kategoria", "pieniadze"]) == 0
    out = capsys.readouterr().out
    assert "liczenie-banknotow" in out and "whoosh" not in out
    assert pr.main(["dzwieki", "--szukaj", "applause"]) == 0 and "oklaski" in capsys.readouterr().out
    assert pr.main(["dzwieki", "--muzyka"]) == 0 and "muzyka-lofi" in capsys.readouterr().out
    assert pr.main(["dzwieki", "--szukaj", "zzzz"]) == 1
    assert pr.main(["dzwieki", "--rola", "narastanie"]) == 0
    out = capsys.readouterr().out
    assert "narastanie-krotkie" in out and "whoosh " not in out and "szczyt" in out
    assert pr.main(["dzwieki", "--kategoria", "gry"]) == 0 and "gra: nie do reklamy" in capsys.readouterr().out


def test_role_szczyty_i_flagi_gier():
    # role (zdanie dźwiękowe, seria), szczyt i flaga „gra” w katalogu zgodne z ROLE/GRA; narastanie ma szczyt na końcu
    kat = {d["id"]: d for d in ed.dzwieki_katalog(LIB)["dzwieki"]}
    assert ed.dzwieki_katalog(LIB)["role"] == dz.ROLE                       # kolejność wyboru (zdanie bierze pierwszy)
    for rola, ids in dz.ROLE.items():
        assert len({kat[i]["sha256"] for i in ids}) == len(ids) >= 2, rola     # seria na zmianę = różne pliki
        assert all(rola in kat[i]["rola"] for i in ids)
    assert all(kat[i]["szczyt"] > 0.8 * kat[i]["dl"] for i in dz.ROLE["narastanie"])
    assert all(kat[i]["szczyt"] < 0.2 for i in ("boom-kinowy", "klik", "pop", "magia"))
    assert kat["power-up"]["gra"] and kat["potwierdzenie"]["gra"] and not kat["klik"]["gra"] and not kat["whoosh"]["gra"]
    assert all("szczyt" not in d for d in kat.values() if d["kat"] == "muzyka")


def test_bledy_wykrywaja_ten_sam_plik_pod_dwiema_nazwami(tmp_path, monkeypatch):
    kat = json.loads((LIB / "katalog.json").read_text(encoding="utf-8"))
    kat["dzwieki"][1]["sha256"] = kat["dzwieki"][0]["sha256"]
    (tmp_path / "katalog.json").write_text(json.dumps(kat), encoding="utf-8")
    monkeypatch.setattr(dz, "KATALOG", tmp_path / "katalog.json")
    assert any("ten sam plik co whoosh" in e for e in dz.bledy())


@pytest.fixture()
def film(tmp_path):
    f = tmp_path / "film.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=25:d=4",
                    "-f", "lavfi", "-i", "sine=d=4", "-shortest", "-pix_fmt", "yuv420p", "-c:a", "aac", str(f)], check=True)
    return f


def proj(f):
    return json.loads(ed.project_path(f).read_text(encoding="utf-8"))


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_agent_dodaje_dzwiek_i_podklad(film, capsys):
    assert pr.main(["dodaj-dzwiek", str(film), "kasa", "--start", "1.5"]) == 0
    assert pr.main(["dodaj-dzwiek", str(film), "muzyka-lofi", "--wyciszanie", "1"]) == 0
    a = proj(film)["audio"]
    assert Path(a[0]["src"]) == film.parent / "dzwieki" / "kasa.mp3" and a[0]["start"] == 1.5 and a[0]["volume"] == 1.0
    assert a[1]["volume"] == 0.3 and a[1]["fadeOut"] == 1.0                     # podkład ciszej, z wyciszeniem
    assert pr.main(["sprawdz", str(film)]) == 0
    # --na: najgłośniejsza chwila efektu w T (narastanie zaczyna się wcześniej); za blisko początku = przycięty początek
    szczyt = next(d for d in ed.dzwieki_katalog(LIB)["dzwieki"] if d["id"] == "narastanie")["szczyt"]
    assert pr.main(["dodaj-dzwiek", str(film), "narastanie", "--na", "3.0"]) == 0
    assert pr.main(["dodaj-dzwiek", str(film), "narastanie", "--na", "1.0"]) == 0
    n1, n2 = proj(film)["audio"][2:]
    assert n1["start"] == pytest.approx(3.0 - szczyt) and n1["in"] == 0
    assert n2["start"] == 0 and n2["in"] == pytest.approx(szczyt - 1.0)
    assert "szczyt na 1.00 s" in capsys.readouterr().out


def test_plan_serii_na_zmiane_ciszej_i_bez_karabinu():
    ruchy = {"whoosh-szybki": 0.157, "whoosh": 0.47, "swoosh": 1.93}
    plan = pr.plan_serii([2.0, 2.2, 2.4, 2.6, 2.8, 3.0], ["pop", "plop"], ruchy)
    assert [x["id"] for x in plan] == ["pop", "plop"] * 3
    assert [x["glosnosc"] for x in plan] == [0.4, 0.37, 0.34, 0.31, 0.28, 0.25]       # schodek jak u shotcraft
    plan = pr.plan_serii([1.0, 1.3, 1.33, 2.0, 2.03, 2.06, 2.09, 2.5], ["pop", "plop"], ruchy)
    assert [(x["id"], x.get("pominiete"), x.get("zamiast")) for x in plan] == [
        ("pop", 0, None), ("plop", 1, None), ("whoosh-szybki", None, 4), ("pop", 0, None)]   # 2 za blisko: pierwszy; 4: whoosh
    assert plan[2]["t"] == pytest.approx(2.045)


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_zdanie_i_seria_na_osi(film, capsys):
    kat = {d["id"]: d for d in ed.dzwieki_katalog(LIB)["dzwieki"]}
    assert pr.main(["zdanie", str(film), "--na", "2.5"]) == 0
    nar, ud, bl = proj(film)["audio"]
    assert Path(nar["src"]).stem == "narastanie" and Path(ud["src"]).stem == "boom-kinowy" and Path(bl["src"]).stem == "magia"
    assert nar["start"] + kat["narastanie"]["szczyt"] - nar["in"] == pytest.approx(2.5)        # szczyty w jednej chwili
    assert nar["start"] == pytest.approx(2.5 - pr.ZDANIE_ROZBIEG) and nar["fadeIn"] > 0      # słychać 1,17 s narastania
    assert ud["start"] + kat["boom-kinowy"]["szczyt"] == pytest.approx(2.5)
    assert bl["start"] + kat["magia"]["szczyt"] == pytest.approx(2.5 + pr.ZDANIE_ODSTEP)
    assert (nar["volume"], ud["volume"], bl["volume"]) == (0.5, 0.9, 0.45)
    assert pr.main(["zdanie", str(film), "--na", "1.0", "--przed", "brak", "--po", "brak"]) == 0
    assert "⚠" not in capsys.readouterr().out
    assert pr.main(["zdanie", str(film), "--na", "3.0", "--przed", "brak", "--po", "brak"]) == 0
    assert "3. głośne uderzenie" in capsys.readouterr().out
    assert pr.main(["seria", str(film), "--czasy", "0.5,0.7,0.9"]) == 0
    seria = proj(film)["audio"][-3:]
    assert [Path(m["src"]).stem for m in seria] == ["pop", "plop", "pop"]
    assert [m["volume"] for m in seria] == [0.4, 0.325, 0.25]
    p = proj(film)
    p["audio"] += [dict(p["audio"][-1]) for _ in range(ed.MAX_AUDIO - len(p["audio"]) - 1)]
    pr.save(film, p)
    with pytest.raises(SystemExit, match="najwyżej 32"):           # edytor pominąłby nadmiar bez słowa
        pr.main(["zdanie", str(film), "--na", "2.0"])


def test_ocena_slyszalnosci_progi_i_porady():
    # tło: głos −20 dB, oddech 2,0–2,5 s; efekty: whoosh tuż przed oddechem, pop w oddechu, klik pod głosem, błysk bez dźwięku
    tlo = [-20.0] * 200 + [-60.0] * 50 + [-20.0] * 350
    env = lambda db, n=20: [db] * n                                                   # noqa: E731
    r = pr.ocena_slyszalnosci([
        {"nazwa": "whoosh", "start": 1.6, "env": env(-22), "glosnosc": 0.6, "rola": ["ruch"]},
        {"nazwa": "pop", "start": 2.1, "env": env(-30), "glosnosc": 0.4, "rola": ["pojawienie"]},
        {"nazwa": "klik", "start": 3.0, "env": env(-35), "glosnosc": 0.5, "rola": ["klik"]},
        {"nazwa": "boom", "start": 4.0, "env": env(-35), "glosnosc": 0.5, "rola": ["uderzenie"]},
        {"nazwa": "magia", "start": 5.0, "env": env(-50), "glosnosc": 0.45, "rola": ["blysk"]}], tlo, 6.0)
    w = {x["nazwa"]: x for x in r["efekty"]}
    assert [w[n]["ocena"] for n in ("whoosh", "pop", "klik", "boom", "magia")] == [
        "slychac", "czysto", "zagluszony", "zagluszony", "brak"]
    assert w["whoosh"]["porada"] == "przesuń szczyt na 2.05 s (cisza w tle)"      # przejście → do oddechu
    assert w["klik"]["porada"] == "głośniej: 1.58"                                  # oddech za daleko (> 0,6 s)
    assert w["boom"]["porada"].startswith("głośniej")                               # zdanie stoi w miejscu
    assert r["przerwy"] == [[2.0, 2.5]] and r["wymagane_czysto"] == 3 and not r["ok"]
    assert any("bez dźwięku" in b or "prawie bez" in b for b in r["bledy"]) and any("czysto słyszalnych 1" in b for b in r["bledy"])
    r = pr.ocena_slyszalnosci([{"nazwa": f"z{i}", "start": 0.5 + i, "env": env(-40), "rola": ["klik"]} for i in range(3)]
                              + [{"nazwa": "x", "start": 2.1, "env": env(-30), "rola": []}], tlo, 6.0)
    assert any("zagłuszonych 3 z 4" in b for b in r["bledy"])


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_slychac_projektu_tym_samym_miksem_co_eksport(film, tmp_path, capsys):
    assert pr.main(["seria", str(film), "--czasy", "0.5,1.0,1.5"]) == 0
    assert pr.main(["zdanie", str(film), "--na", "2.5", "--przed", "brak"]) == 0
    raport = tmp_path / "slychac.json"
    kod = pr.main(["slychac", str(film), "--json", str(raport)])
    r = json.loads(raport.read_text(encoding="utf-8"))
    assert kod == (0 if r["ok"] else 1) and len(r["efekty"]) == 5
    assert all(-25 < e["tlo_db"] < -16 for e in r["efekty"])            # sinus z klipu (ok. −21 dBFS) bez efektów
    assert [e["nazwa"] for e in r["efekty"]][:3] == ["pop", "plop", "pop"]
    assert r["efekty"][0]["efekt_db"] > r["efekty"][2]["efekt_db"]     # seria coraz ciszej
    out = capsys.readouterr().out
    assert "względem tła" in out and "Wynik:" in out


@pytest.mark.skipif(not (HAS_FF and shutil.which("node")), reason="brak ffmpeg albo node")
def test_slychac_cues_filmu_z_kodu(tmp_path, capsys):
    # zastępczy sound.mjs z tym samym mix(): test nie zależy od zainstalowanego skilla animacji
    (tmp_path / "sound.mjs").write_text(
        "export function mix(cues, dur) { const n = Math.round(dur * 48000), L = new Float32Array(n), R = new Float32Array(n);"
        " for (const c of cues) { const v = c.vol ?? .5, i0 = Math.round(c.t * 48000);"
        " for (let i = 0; i < 9600 && i0 + i < n; i++) { L[i0 + i] += v * Math.sin(i / 3); R[i0 + i] += v * Math.sin(i / 3); } }"
        " return [L, R]; }\n", encoding="utf-8")
    (tmp_path / "cues.json").write_text(json.dumps([{"sfx": "pop", "t": 0.5}, {"sfx": "whoosh", "t": 1.2, "vol": 0.01}]))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:d=2", str(tmp_path / "bed.wav")], check=True)
    raport = tmp_path / "r.json"
    pr.main(["slychac", "--cues", str(tmp_path / "cues.json"), "--bed", str(tmp_path / "bed.wav"),
             "--sound", str(tmp_path / "sound.mjs"), "--json", str(raport)])
    pop, whoosh = json.loads(raport.read_text(encoding="utf-8"))["efekty"]
    assert 0.5 <= pop["t"] <= 0.7 and pop["ocena"] == "czysto"   # stała głośność 0,2 s: szczyt gdzieś w tym czasie
    assert whoosh["ocena"] == "zagluszony" and whoosh["rola"] == ["ruch"]
    assert pop["tlo_db"] == pytest.approx(-27, abs=2)                               # sinus −21 dBFS × bed-vol 0,5


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_wyodrebnij_dzwiek_klipu_i_innego_filmu(film, tmp_path):
    pr.save(film, {"version": 1, "canvas": {"w": 320, "h": 240, "fps": 25}, "texts": [], "audio": [],
                   "clips": [{"id": "c1", "src": str(film), "kind": "video", "in": 0, "out": 1},
                             {"id": "c2", "src": str(film), "kind": "video", "in": 2, "out": 4, "fadeOut": 0.5}]})
    assert pr.main(["wyodrebnij", str(film), "c2"]) == 0
    p = proj(film)
    m = p["audio"][0]
    # dźwięk klipu zostaje w tym samym miejscu osi jako osobne audio (AAC skopiowane bez straty), klip wyciszony
    assert (m["start"], m["in"], m["out"], m.get("fadeOut")) == (1.0, 2, 4, 0.5)
    assert Path(m["src"]).suffix == ".m4a" and ed.probe(Path(m["src"]))["acodec"] == "aac"
    assert p["clips"][1]["muted"] is True and not p["clips"][0].get("muted")
    with pytest.raises(SystemExit, match="wyciszony"):
        pr.main(["wyodrebnij", str(film), "c2"])
    assert pr.main(["wyodrebnij", str(film), "--plik", str(film), "--start", "0.5"]) == 0
    assert proj(film)["audio"][1]["start"] == 0.5
    cisza = tmp_path / "cisza.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=64x64:r=25:d=1", str(cisza)], check=True)
    with pytest.raises(SystemExit, match="nie ma dźwięku"):
        pr.main(["wyodrebnij", str(film), "--plik", str(cisza)])
    p = proj(film)
    assert ed.normalize(p, pr.resolve)["audio"][0]["src"] == Path(m["src"])     # eksport przyjmuje wyodrębniony plik


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_nagranie_z_przegladarki_na_aac(tmp_path):
    src = tmp_path / "nagranie.webm"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:d=1", "-c:a", "libopus", str(src)], check=True)
    dest = tmp_path / "out.m4a"
    subprocess.run(ed.nagranie_cmd(src, dest), check=True, capture_output=True)
    info = ed.probe(dest)
    assert info["acodec"] == "aac" and info["duration"] == pytest.approx(1.0, abs=0.1) and ed.media_kind(dest) == "audio"


def test_menu_audio_w_edytorze():
    # edytor woła te same endpointy, a Wideograf dostaje w prośbie z edytora polecenia biblioteki
    js = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "hq" / "web" / "src").glob("*.js")))
    for ep in ("/edit/dzwieki", "/edit/dzwiek-plik", "/edit/dzwiek`", "/edit/muzyka", "/edit/wyodrebnij", "/edit/lektor", "/edit/nagranie"):
        assert ep in js, ep
    api = (ROOT / "hq" / "plugin" / "plugin_api.py").read_text(encoding="utf-8")
    for ep in ("/edit/dzwieki", "/edit/dzwiek-plik", '"/edit/dzwiek"', "/edit/muzyka", "/edit/wyodrebnij", "/edit/lektor", "/edit/nagranie"):
        assert ep in api, ep
    assert "projekt.py dodaj-dzwiek" in js and "wyodrebnij" in js
