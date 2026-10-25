"""Czysty głos (edytor.glos_filter): trzy poziomy, próg odszumiania z tła nagrania, osobne wejście dźwięku z zapasem
i bez opóźnienia afftdn w eksporcie edytora HQ, projekt.py glos, montaz.py glos, clipmaker --glos."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO, load_script

ed = load_script("hq/plugin/edytor.py", "jarvo_edytor_glos_test")
pr = load_script("profiles/jarvo-wideo/scripts/projekt.py", "jarvo_projekt_glos_test")
K = load_script("profiles/jarvo-wideo/scripts/klipy.py", "jarvo_klipy_glos_test")
sys.path.insert(0, str(REPO / "profiles" / "jarvo-wideo" / "scripts"))
import montaz  # noqa: E402
import wideo_lib as wl  # noqa: E402


def _ff(*filtry: str) -> bool:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return False
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return all(f" {f} " in out for f in filtry)


def test_lancuchy_poziomow():
    lekki, sredni, mocny = (ed.glos_filter(p, -47.2) for p in ed.GLOS)
    assert lekki.startswith("highpass=f=80") and "afftdn" not in lekki and "agate" not in lekki   # tło zostaje
    assert "deesser=i=0.4,afftdn=nr=20:nf=-41," in sredni                                    # tło + 6 dB
    assert f"agate=threshold={10 ** (-41.2 / 20):.5f}:ratio=2:range=0.35" in sredni           # ekspander: tło + 6 dB
    assert sredni.index("afftdn") < sredni.index("agate") < sredni.index("acompressor")
    assert "afftdn=nr=25:nf=-35," in mocny and "alimiter=limit=0.891251" in mocny and mocny.count("acompressor") == 2
    assert "makeup=3" in mocny and "range=0.18" in mocny
    assert "nf=-44" in ed.glos_filter("sredni")                                                 # bez pomiaru: GLOS_TLO
    assert "nf=-80" in ed.glos_filter("sredni", -120) and "nf=-20" in ed.glos_filter("mocny", -10)   # zakres afftdn
    assert ed.glos_filter(None) == ed.glos_filter("glosno") == ""
    assert [ed.glos_opoznienie(p) for p in (None, *ed.GLOS)] == [0, 0, ed.GLOS_OPOZNIENIE, ed.GLOS_OPOZNIENIE]
    assert [ed.glos_auto(t) for t in (None, -70, -60, -50, -42, -35)] == ["sredni", "lekki", "lekki", "sredni", "sredni", "mocny"]


def test_pomiar_tla():
    cmd = ed.szum_cmd(Path("/x/a.mp4"), a=12, d=5000)
    assert cmd[cmd.index("-ss") + 1] == "12" and cmd[cmd.index("-t") + 1] == str(int(ed.SZUM_MAX))
    assert "highpass=f=80,asetnsamples=n=2400" in cmd[cmd.index("-af") + 1]
    okna = [-62.0 + i * 0.4 for i in range(100)]                  # najcichsze 10% okien = tło
    log = "\n".join([f"lavfi.astats.Overall.RMS_level={v:.2f}" for v in okna] + ["lavfi.astats.Overall.RMS_level=-inf"] * 50)
    assert ed.szum_z_logu(log) == -58.0
    assert ed.szum_z_logu("lavfi.astats.Overall.RMS_level=-40\n" * 5) is None


def _res(s):
    return Path(s) if Path(s).is_file() else None


def _projekt(tmp_path, **kw):
    a = tmp_path / "nagranie.mp4"
    a.write_bytes(b"x")
    m = tmp_path / "lektor.wav"
    m.write_bytes(b"x")
    base = {"src": str(a), "speed": 1, "volume": 1}
    raw = {"clips": [{**base, "in": 0.3, "out": 5.0, "voice": "sredni"}, {**base, "in": 5.0, "out": 9.0, "voice": "sredni"},
                     {**base, "in": 20, "out": 24, "voice": "nie-ma"}],
           "audio": [{"src": str(m), "start": 1.0, "in": 2.0, "out": 6.0, "volume": 0.8, "voice": "lekki"}], **kw}
    return ed.normalize(raw, _res), str(a), str(m)


def test_projekt_i_ciaglosc(tmp_path):
    p, a, m = _projekt(tmp_path)
    assert [c.get("voice") for c in p["clips"]] == ["sredni", "sredni", None] and p["audio"][0]["voice"] == "lekki"
    assert ed.ciagly(p["clips"][0], p["clips"][1])                        # podział z tym samym głosem: bez wyciszenia
    assert not ed.ciagly(p["clips"][0], {**p["clips"][1], "voice": "mocny"})
    assert ed.szum_zakresy(p) == {a: (0.0, 39.0)}       # klipy 0,3–9 s + 30 s zapasu; lekki nie odszumia: bez pomiaru


def test_eksport_osobne_wejscie_bez_opoznienia(tmp_path):
    p, a, m = _projekt(tmp_path)
    cmd = ed.build_command(p, {a: True}, [], tmp_path / "o.mp4", szum={a: -47.2})
    wej = [i for i, x in enumerate(cmd) if x == "-i"]
    srcs = [cmd[i + 1] for i in wej]
    assert srcs == [a, a, a, a, a, m]                    # klip 1 (obraz, dźwięk), klip 2 (obraz, dźwięk), klip 3, audio
    ss = lambda k: float(cmd[wej[k] - 3]); tt = lambda k: float(cmd[wej[k] - 1])   # noqa: E731
    assert ss(1) == 0.0 and tt(1) == pytest.approx(4.7 + 0.3 + 0.025 + 0.05)     # zapas tylko tyle, ile jest przed klipem
    assert ss(3) == 4.0 and tt(3) == pytest.approx(4.0 + 1.0 + 0.025 + 0.05)     # pełny zapas 1 s
    g = cmd[cmd.index("-filter_complex") + 1]
    a0 = g[g.index("[1:a]"):g.index("[a0]")]
    assert "afftdn=nr=20:nf=-41" in a0 and "atrim=start=0.325" in a0             # zapas + opóźnienie afftdn ścięte
    assert a0.index("highpass") < a0.index("atrim=start") < a0.index("aresample")
    a1 = g[g.index("[3:a]"):g.index("[a1]")]
    assert "atrim=start=1.025" in a1
    assert "[4:a]" in g and "highpass" not in g[g.index("[4:a]"):g.index("[a2]")]  # zły poziom = bez czyszczenia
    au = g[g.index("[5:a]"):g.index("[m0]")]
    assert "acompressor=threshold=-18dB:ratio=2" in au and "atrim=start=1,asetpts=PTS-STARTPTS,atrim=duration=4" in au
    bez = ed.build_command(ed.normalize({"clips": [{"src": a, "in": 0, "out": 2}]}, _res), {a: True}, [], tmp_path / "o.mp4")
    assert bez.count("-i") == 1 and "highpass" not in " ".join(bez)


def test_probka_do_odsluchu(tmp_path):
    cmd = ed.glos_probka_cmd(Path("/x/a.mp4"), 12.0, 8.0, "mocny", -40.0, tmp_path / "p.mp3")
    assert cmd[cmd.index("-c:a") + 1] == "libmp3lame"                 # MP3 gra też w Chromium bez AAC
    assert cmd[cmd.index("-ss") + 1] == "11" and "afftdn=nr=25:nf=-28" in cmd[cmd.index("-af") + 1]
    assert cmd[cmd.index("-af") + 1].endswith("atrim=start=1.025,asetpts=PTS-STARTPTS,atrim=duration=8")


def test_interfejs_edytora():
    js = (REPO / "hq" / "web" / "src" / "45-edytor.js").read_text(encoding="utf-8")
    m = re.search(r"const ED_GLOS = \[\[null, [^\]]+\], (.+?)\];", js)
    assert m and re.findall(r'\["(\w+)"', m.group(1)) == list(ed.GLOS)
    assert 'glosTools("clip", c)' in js and 'glosTools("audio", m)' in js
    api = (REPO / "hq" / "plugin" / "plugin_api.py").read_text(encoding="utf-8")
    assert '"/edit/glos-tlo"' in api and '"/edit/glos-probka"' in api and "szum=szum)" in api


def test_projekt_glos(tmp_path, monkeypatch, capsys):
    film = tmp_path / "film.mp4"
    film.write_bytes(b"x")
    monkeypatch.setattr(pr.ed, "probe", lambda p: {"ok": True, "duration": 10.0, "w": 1920, "h": 1080, "fps": 30, "audio": True})
    monkeypatch.setattr(pr, "tlo_nagrania", lambda src, a, b: -38.0)
    pr.main(["glos", str(film), "--wszystkie"])
    proj = json.loads(pr.ed.project_path(film).read_text(encoding="utf-8"))
    assert proj["clips"][0]["voice"] == "mocny" and "tło nagrania -38 dB" in capsys.readouterr().out
    cid = proj["clips"][0]["id"]
    pr.main(["glos", str(film), cid, "--poziom", "lekki"])
    pr.main(["pokaz", str(film)])
    assert "czysty głos lekki" in capsys.readouterr().out
    pr.main(["glos", str(film), cid, "--poziom", "brak"])
    assert "voice" not in json.loads(pr.ed.project_path(film).read_text(encoding="utf-8"))["clips"][0]


def test_montaz_glos(tmp_path, monkeypatch):
    src = tmp_path / "n.mp4"
    src.write_bytes(b"x")
    cmds = []
    monkeypatch.setattr(montaz, "has_audio", lambda p: True)
    monkeypatch.setattr(wl, "duration", lambda p: 30.0)
    monkeypatch.setattr(wl, "run", lambda cmd, **kw: cmds.append(cmd))
    monkeypatch.setattr(montaz.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(
        cmd, 0, "", "lavfi.astats.Overall.RMS_level=-48.0\n" * 20))
    out, stats = montaz.voice(src, tmp_path / "o.mp4", "auto")
    assert stats == {"poziom": "sredni", "tlo_db": -48.0}
    c = cmds[0]
    assert c[c.index("-c:v") + 1] == "copy" and "1:a:0" in c and "0:v?" in c
    af = c[c.index("-af") + 1]
    assert "afftdn=nr=20:nf=-42" in af and "atrim=start=0.025" in af and "apad=whole_dur=30.000" in af


def test_clipmaker_mierzy_glosnosc_po_czyszczeniu(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(K.subprocess, "run", lambda cmd, **kw: seen.append(cmd) or subprocess.CompletedProcess(
        cmd, 0, "", "Summary:\n I: -20.0 LUFS\n Peak: -3.0 dBFS"))
    assert K.glosnosc_zrodla(tmp_path / "a.mp4", [(1.0, 5.0)], ed.glos_filter("sredni", -47)) == (-20.0, -3.0)
    af = seen[0][seen[0].index("-af") + 1]
    assert af.index("asetpts=N/SR/TB,highpass") < af.index("aresample=48000")
    src = (REPO / "profiles" / "jarvo-wideo" / "scripts" / "klipy.py").read_text(encoding="utf-8")
    assert 'c["voice"] = glos' in src and '"--glos"' in src


@pytest.mark.skipif(not _ff("afftdn", "agate", "deesser"), reason="ffmpeg z afftdn, agate i deesser (obraz Hermesa)")
def test_eksport_cichsze_pauzy_i_usta_w_czasie(tmp_path):
    """Ton w zdaniach + szum różowy: po „średnim” pauzy ciszej o ≥ 6 dB, a początek tonu w tym samym miejscu (± 5 ms)."""
    film = tmp_path / "n.mp4"
    ton = "sine=f=440:r=48000:d=12,volume='if(between(mod(t,4),1,3),2.4,0)':eval=frame"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=320x240:r=25:d=12",
                    "-f", "lavfi", "-i", ton, "-f", "lavfi", "-i", "anoisesrc=c=pink:a=0.02:r=48000:d=12:seed=7",
                    "-filter_complex", "[1:a][2:a]amix=inputs=2:normalize=0[a]", "-map", "0:v", "-map", "[a]",
                    "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k", "-shortest", str(film)], check=True)
    tlo = ed.szum_z_logu(subprocess.run(ed.szum_cmd(film), capture_output=True, text=True).stderr)
    assert tlo is not None and -60 < tlo < -35

    def eksport(voice):
        p = ed.normalize({"canvas": {"w": 320, "h": 240, "fps": 25},
                          "clips": [{"src": str(film), "in": 4.5, "out": 11.5, **({"voice": voice} if voice else {})}]}, _res)
        out = tmp_path / f"{voice or 'bez'}.mp4"
        cmd = [x for x in ed.build_command(p, {str(film): True}, [], out, szum={str(film): tlo}) if x not in ("-progress", "pipe:1")]
        subprocess.run(cmd, check=True)
        return out

    def rms(plik, a, d):
        r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-ss", str(a), "-t", str(d), "-i", str(plik), "-af",
                            "astats=metadata=1:reset=0,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
                            "-f", "null", "-"], capture_output=True, text=True)
        return float(re.findall(r"RMS_level=(-?[\d.]+)", r.stdout)[-1])

    def poczatek(plik):                       # pierwsza chwila tonu po pauzie (oś: 4,5 s źródła → 0)
        r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(plik), "-af", "silencedetect=n=-30dB:d=0.3",
                            "-f", "null", "-"], capture_output=True, text=True)
        return [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    bez, sredni = eksport(None), eksport("sredni")
    pauza = (rms(sredni, 2.8, 1.4), rms(bez, 2.8, 1.4))           # oś 2,8–4,2 s = pauza 7,3–8,7 s źródła
    assert pauza[0] < pauza[1] - 6, pauza
    p0, p1 = poczatek(sredni), poczatek(bez)
    assert len(p0) == len(p1) >= 2 and all(abs(x - y) < 0.005 for x, y in zip(p0, p1)), (p0, p1)


# ------------------------------------------------------------------ głos Jarva w aplikacji natywnie (hq/plugin/glos.py)

def test_glos_aplikacji_z_programu_floty(monkeypatch, tmp_path):
    """Natywnie lektor aplikacji to program floty z PATH panelu (`<program>/bin-floty/jarvo-tts`, na Windows .exe,
    tu atrapa .cmd), bez /opt/jarvo/bin z obrazu; JARVO_TTS wygrywa."""
    import atrapy
    G = load_script("hq/plugin/glos.py", "jarvo_test_glos_natywnie")
    floty = tmp_path / "program" / "bin-floty"
    atrapy.program(floty, "jarvo-tts", "print('ok')")
    monkeypatch.setenv("PATH", atrapy.sciezka(floty, reszta=False))
    monkeypatch.delenv("JARVO_TTS", raising=False)
    assert Path(G.program_glosu()).parent == floty
    monkeypatch.setenv("JARVO_TTS", str(atrapy.program(tmp_path / "inny", "jarvo-tts", "print('ok')")))
    assert Path(G.program_glosu()).parent == tmp_path / "inny"


def test_glos_aplikacji_przypina_lektora_do_zadania(monkeypatch):
    """Lektor aplikacji startuje w przenosne.uruchom z przy_starcie, które woła edytor.przypnij_drzewo: na Windows
    własny Job Object, więc restart albo upadek dashboardu nie zostawia jarvo-tts z Pythonem w tle; limit czasu =
    BladGlosu po edytor.zabij_drzewo całego drzewa (nie czeka na zamknięcie uchwytu z obiektem procesu)."""
    import asyncio
    G = load_script("hq/plugin/glos.py", "jarvo_test_glos_zadanie")
    widziane, przypiete, zabite = {}, [], []
    ed = G._edytor()
    monkeypatch.setattr(ed, "przypnij_drzewo", lambda proc: przypiete.append(proc) or True)
    monkeypatch.setattr(ed, "zabij_drzewo", lambda proc: zabite.append(proc))

    class P:
        DEVNULL = subprocess.DEVNULL

        async def uruchom(self, argv, **kw):
            widziane.update(kw, argv=argv)
            kw["przy_starcie"](f"proc-{len(przypiete)}")
            if kw.get("timeout") == 0.01:
                raise asyncio.TimeoutError
            return 0, b"", b""

    monkeypatch.setattr(G, "_przenosne", lambda: P())
    assert asyncio.run(G._uruchom(["jarvo-tts", "Dzień dobry.", "-o", "a.wav"], 5)) == 0
    assert przypiete == ["proc-0"] and zabite == [] and widziane["argv"][0] == "jarvo-tts"
    with pytest.raises(G.BladGlosu):
        asyncio.run(G._uruchom(["jarvo-tts", "x"], 0.01))
    assert przypiete == ["proc-0", "proc-1"] and zabite == ["proc-1"]
