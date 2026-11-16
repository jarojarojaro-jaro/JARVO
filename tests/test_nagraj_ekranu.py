"""Nagrywanie pracy na ekranie Komputera (skill praca-na-ekranie, nagraj.py): krótkie segmenty z twardym limitem,
strażnik zamyka segment przy odmowie, pauzie i ciszy, film tylko z udanych. Bez ffmpeg i bez pulpitu: atrapy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import load_script

N = load_script("profiles/jarvo/skills/ekran/praca-na-ekranie/scripts/nagraj.py")


class Zegar:
    def __init__(self, t: float = 1_000_000.0):
        self.t = t
        self.przy_spaniu = []              # funkcje wołane przy każdym _spij (np. dopisanie wpisu do dziennika)

    def teraz(self) -> float:
        return self.t

    def spij(self, s: float) -> None:
        self.t += s
        for f in list(self.przy_spaniu):
            f()


class AtrapaFfmpeg:
    def __init__(self, argv, plik: Path | None = None):
        self.argv = argv
        self.pid = 4242
        self.kod = None
        self.wejscie = b""
        if plik is not None:
            plik.write_bytes(b"\x1a\x45\xdf\xa3 nagranie")
        atrapa = self

        class Stdin:
            def write(self, b):
                atrapa.wejscie += b

            def flush(self):
                pass

            def close(self):
                if b"q" in atrapa.wejscie:
                    atrapa.kod = 0

        self.stdin = Stdin()

    def poll(self):
        return self.kod

    def wait(self, _t=None):
        return self.kod

    def kill(self):
        self.kod = -9


@pytest.fixture
def otoczenie(tmp_path, monkeypatch):
    """Instalacja Jarva w tmp: Komputer z oknem na DISPLAY :7, ffmpeg „w PATH”, strażnik nieuruchamiany."""
    root = tmp_path / "root"
    dane = root / "dane" / "jarvo"
    (dane / "komputer").mkdir(parents=True)
    (root / "stan" / "komputer").mkdir(parents=True)
    (root / "stan" / "komputer" / "ustawienia.json").write_text(json.dumps(
        {"wlaczony": True, "okno": True, "ekran": {"DISPLAY": ":7", "XAUTHORITY": "/tmp/xauth"}}), encoding="utf-8")
    monkeypatch.setenv("JARVO_ROOT", str(root))
    monkeypatch.setenv("JARVO_DATA_DIR", str(dane))
    monkeypatch.setattr(N, "WINDOWS", False)
    monkeypatch.setattr(N, "MACOS", False)
    monkeypatch.setattr(N, "_program", lambda nazwa: f"/opt/bin/{nazwa}")
    zegar = Zegar()
    monkeypatch.setattr(N, "_teraz", zegar.teraz)
    monkeypatch.setattr(N, "_spij", zegar.spij)
    straze = []
    monkeypatch.setattr(N, "_odpal_straz", lambda k, nr: straze.append(nr))
    k = tmp_path / "nagranie"
    return {"k": k, "zegar": zegar, "straze": straze, "dziennik": dane / "komputer" / "dziennik.jsonl",
            "pauza": dane / "komputer" / "pauza", "root": root}


def _wpis(dziennik: Path, **w) -> None:
    with open(dziennik, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": "2026-11-17T10:00:00+00:00", "sesja": 2, **w}) + "\n")


def _pilnuj(o, monkeypatch, nr: int = 1) -> tuple[dict, AtrapaFfmpeg]:
    ff = {}

    def uruchom(argv, env, log):
        ff["p"] = AtrapaFfmpeg(argv, o["k"] / f"seg-{nr:02d}.mkv")
        ff["env"] = env
        return ff["p"]

    monkeypatch.setattr(N, "_uruchom_ffmpeg", uruchom)
    s = N.pilnuj(o["k"], nr)
    return s, ff["p"]


# ------------------------------------------------------------------ segment: twardy limit i ekran Komputera

def test_segment_ma_twardy_limit_ffmpeg(otoczenie):
    o = otoczenie
    _wpis(o["dziennik"], narzedzie="click", decyzja="tak")      # stary wpis sprzed startu: nie liczy się
    w = N.start(o["k"], "Logowanie: formularz")
    assert w["ok"] and w["segment"] == 1 and w["maks_s"] == N.MAKS_SEGMENT == 75 and o["straze"] == [1]
    seg = N.wczytaj(o["k"])["segmenty"][0]
    argv = seg["ffmpeg"]
    assert argv[argv.index("-t") + 1] == str(N.MAKS_SEGMENT)
    assert argv.index("-t") > argv.index("-i")                   # limit wyjścia, nie wejścia
    assert argv[argv.index("-f") + 1] == "x11grab" and argv[argv.index("-i") + 1] == ":7"
    assert argv[argv.index("-threads") + 1] == "2"
    assert argv[argv.index("/opt/bin/ffmpeg") - 3:argv.index("/opt/bin/ffmpeg")] == ["/opt/bin/nice", "-n", "15"]
    assert seg["env"] == {"DISPLAY": ":7", "XAUTHORITY": "/tmp/xauth"}
    assert seg["status"] == "nagrywa" and seg["dziennik_od"] == o["dziennik"].stat().st_size


def test_start_odmawia_bez_okna_komputera_i_przy_pauzie(otoczenie, capsys):
    o = otoczenie
    ust = o["root"] / "stan" / "komputer" / "ustawienia.json"
    ust.write_text(json.dumps({"wlaczony": True, "okno": False}), encoding="utf-8")
    assert N.main(["start", "krok", "--katalog", str(o["k"])]) == 1
    assert "okno on" in json.loads(capsys.readouterr().out)["blad"]
    ust.write_text(json.dumps({"wlaczony": True, "okno": True, "ekran": {"DISPLAY": ":7"}}), encoding="utf-8")
    o["pauza"].write_text("{}", encoding="utf-8")
    with pytest.raises(N.Blad, match="wstrzymany"):
        N.start(o["k"], "krok")
    assert o["straze"] == []


# ------------------------------------------------------------------ strażnik

def test_straz_konczy_segment_jako_nieudany_przy_odmowie(otoczenie, monkeypatch):
    o = otoczenie
    N.start(o["k"], "Rejestracja: weryfikacja")
    wpisy = iter([{"narzedzie": "click", "decyzja": "tak", "cel": "Zarejestruj"},
                  {"narzedzie": "click", "decyzja": "odmowa", "zasada": "weryfikacja_czlowieka"}])
    o["zegar"].przy_spaniu.append(lambda: (w := next(wpisy, None)) and _wpis(o["dziennik"], **w))
    s, ff = _pilnuj(o, monkeypatch)
    assert s["status"] == "nieudany" and "odmowa (weryfikacja_czlowieka)" in s["powod"]
    assert s["kroki_komputera"] == 1
    assert ff.wejscie == b"q"                                    # ffmpeg zamknięty od razu
    assert not (o["k"] / "seg-01.mkv").exists()                  # nagranie pętli nie zostaje
    assert not (o["k"] / "seg-01.straz").exists()


def test_straz_konczy_segment_przy_ciszy_bez_krokow(otoczenie, monkeypatch):
    o = otoczenie
    N.start(o["k"], "Krok na telefonie zamiast w Komputerze")
    s, ff = _pilnuj(o, monkeypatch)
    assert s["status"] == "nieudany" and "brak kroków" in s["powod"]
    assert N.CISZA <= s["dlugosc_s"] < N.CISZA + 1 and ff.wejscie == b"q"


def test_straz_cisza_po_krokach_zamyka_udany_bez_ogona(otoczenie, monkeypatch):
    o = otoczenie
    N.start(o["k"], "Wyszukiwanie")
    wpisy = iter([None, None, {"narzedzie": "type", "decyzja": "tak"}])
    o["zegar"].przy_spaniu.append(lambda: (w := next(wpisy, None)) and _wpis(o["dziennik"], **w))
    s, _ff = _pilnuj(o, monkeypatch)
    assert s["status"] == "ok" and s["powod"].startswith("cisza")
    assert s["uzyteczne_s"] == pytest.approx(1.5 + N.ZAPAS_PO_KROKU)
    assert (o["k"] / "seg-01.mkv").exists()


def test_straz_pauza_i_ster_odmowa(otoczenie, monkeypatch):
    o = otoczenie
    N.start(o["k"], "Krok")
    _wpis(o["dziennik"], narzedzie="ster", decyzja="odmowa", zasada="klatka_bez_tokenu")   # nie krok agenta
    o["zegar"].przy_spaniu.append(lambda: o["pauza"].write_text("{}", encoding="utf-8"))
    s, _ff = _pilnuj(o, monkeypatch)
    assert s["status"] == "nieudany" and "pauza" in s["powod"]


def test_straz_limit_ffmpeg_konczy_udany(otoczenie, monkeypatch):
    o = otoczenie
    N.start(o["k"], "Długi krok")
    ff = {}

    def uruchom(argv, env, log):
        ff["p"] = AtrapaFfmpeg(argv, o["k"] / "seg-01.mkv")
        ff["p"].kod = 0                                          # ffmpeg sam skończył po -t
        return ff["p"]

    monkeypatch.setattr(N, "_uruchom_ffmpeg", uruchom)
    s = N.pilnuj(o["k"], 1)
    assert s["status"] == "ok" and s["powod"] == f"limit {N.MAKS_SEGMENT} s"


# ------------------------------------------------------------------ start/stop

def _udawany_straz(o, wyniki: dict | None = None):
    """Przy każdym _spij: segment z plikiem stop zamyka się tak, jak zamknąłby go strażnik."""
    def krok():
        for s in N.wczytaj(o["k"])["segmenty"]:
            stop = o["k"] / f"seg-{s['nr']:02d}.stop"
            if s["status"] == "nagrywa" and stop.exists():
                (o["k"] / s["plik"]).write_bytes(b"x")
                nieudany = json.loads(stop.read_text(encoding="utf-8"))["nieudany"]
                N.zakoncz_segment(o["k"], s["nr"], "nieudany" if nieudany else "ok",
                                  "stop --nieudany" if nieudany else "stop")
    o["zegar"].przy_spaniu.append(krok)


def test_nowy_start_zamyka_poprzedni_segment(otoczenie):
    o = otoczenie
    _udawany_straz(o)
    N.start(o["k"], "Krok 1")
    w = N.start(o["k"], "Krok 2")
    assert w["segment"] == 2 and w["poprzedni"]["nr"] == 1 and w["poprzedni"]["status"] == "ok"
    seg = N.wczytaj(o["k"])["segmenty"]
    assert [s["status"] for s in seg] == ["ok", "nagrywa"] and o["straze"] == [1, 2]
    w = N.stop(o["k"], nieudany=True)
    assert w["nr"] == 2 and w["status"] == "nieudany" and not w["do_filmu"]
    w = N.stop(o["k"], nieudany=False)                           # nic nie nagrywa: ostatni segment bez zmian
    assert w["juz_zakonczony"] and w["status"] == "nieudany"


def test_stop_nie_zmienia_segmentu_zamknietego_przez_straznika(otoczenie):
    o = otoczenie
    N.start(o["k"], "Krok")
    N.zakoncz_segment(o["k"], 1, "nieudany", "Komputer: czlowiek (weryfikacja_czlowieka)")
    w = N.stop(o["k"], nieudany=False)
    assert w["status"] == "nieudany" and w["juz_zakonczony"] and not w["do_filmu"]


def test_martwy_straznik_konczy_segment(otoczenie):
    o = otoczenie
    N.start(o["k"], "Krok")
    o["zegar"].t += N.MARTWY + 1
    st = N.stan_nagrania(o["k"])
    assert st["nagrywa"] is None and st["segmenty"][0]["status"] == "nieudany"


def test_limit_segmentow(otoczenie):
    o = otoczenie
    N.zapisz(o["k"], {"segmenty": [{"nr": i, "opis": "x", "plik": f"seg-{i:02d}.mkv", "status": "ok",
                                    "start_ts": 0} for i in range(1, N.MAKS_SEGMENTOW + 1)]})
    with pytest.raises(N.Blad, match="limit"):
        N.start(o["k"], "Krok")


# ------------------------------------------------------------------ film

def _segmenty(o, statusy: list[str]) -> None:
    seg = []
    for i, status in enumerate(statusy, 1):
        plik = f"seg-{i:02d}.mkv"
        if status == "ok":
            (o["k"] / plik).parent.mkdir(parents=True, exist_ok=True)
            (o["k"] / plik).write_bytes(b"x")
        seg.append({"nr": i, "opis": f"Krok {i}", "plik": plik, "status": status, "start_ts": 0,
                    "dlugosc_s": 30.0, "uzyteczne_s": 2.0 if i == 3 else 30.0})
    N.zapisz(o["k"], {"segmenty": seg})


def test_film_tylko_z_udanych_segmentow(otoczenie, monkeypatch):
    o = otoczenie
    _segmenty(o, ["ok", "nieudany", "ok"])
    wywolania = []

    def uruchom(argv):
        wywolania.append(argv)
        Path(argv[-1]).write_bytes(b"mp4")
        return type("W", (), {"returncode": 0, "stderr": b""})()

    monkeypatch.setattr(N, "_uruchom", uruchom)
    w = N.film(o["k"])
    (argv,) = wywolania
    wejscia = [argv[i + 1] for i, a in enumerate(argv) if a == "-i"]
    assert wejscia == [str(o["k"] / "seg-01.mkv"), str(o["k"] / "seg-03.mkv")]
    graf = argv[argv.index("-filter_complex") + 1]
    assert "concat=n=2:v=1:a=0" in graf and "setpts=(PTS-STARTPTS)/6.000" in graf   # 30 s → 5 s
    assert argv[argv.index("-pix_fmt") + 1] == "yuv420p" and argv[argv.index("-c:v") + 1] == "libx264"
    assert w["ok"] and Path(w["film"]) == (o["k"] / "film.mp4").resolve() and (o["k"] / "film.mp4").exists()
    assert w["dlugosc_s"] == pytest.approx(N.MAKS_UJECIE + 2.0)
    assert [u["nr"] for u in w["ujecia"]] == [1, 3] and [p["nr"] for p in w["pominiete"]] == [2]


def test_film_bez_udanych_segmentow_to_blad(otoczenie, monkeypatch, capsys):
    o = otoczenie
    _segmenty(o, ["nieudany", "nieudany"])
    monkeypatch.setattr(N, "_uruchom", lambda argv: pytest.fail("ffmpeg bez udanych segmentów"))
    assert N.main(["film", "--katalog", str(o["k"])]) == 1
    assert "brak udanych" in json.loads(capsys.readouterr().out)["blad"]
    assert not (o["k"] / "film.mp4").exists()


def test_wyczysc_usuwa_robocze_nagrania(otoczenie):
    o = otoczenie
    _segmenty(o, ["ok"])
    (o["k"] / "film.mp4").write_bytes(b"mp4")
    w = N.wyczysc(o["k"], z_filmem=False)
    assert w["film_zostal"] and sorted(p.name for p in o["k"].iterdir()) == ["film.mp4"]
    N.wyczysc(o["k"], z_filmem=True)
    assert not o["k"].exists()
