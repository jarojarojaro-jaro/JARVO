"""Konwerter plików floty (shared/skills/konwersja-plikow): rozmiary, strony, trasy, polecenia silników, CLI.

Silniki (Pillow, ffmpeg, pandoc…) są tu podstawione: trasy i polecenia sprawdzamy bez narzędzi. Prawdziwe konwersje
na końcu, gdy narzędzie jest na maszynie (w obrazie Jarva są wszystkie poza LibreOffice).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import load_script

K = load_script("shared/skills/konwersja-plikow/scripts/konwertuj.py")

PIL_WEJ = {"jpg", "png", "webp", "heic", "gif", "tiff"}
PIL_WYJ = {"jpg", "png", "webp", "heic", "gif", "tiff", "pdf", "ico"}
ENKODERY = """ V..... libx264   H.264
 V..... libvpx-vp9  VP9
 A..... libmp3lame  MP3
 A..... libopus     Opus
 A..... aac         AAC
"""
DEKODERY = " V..... librsvg  SVG\n"


@pytest.fixture
def silniki(monkeypatch):
    """Ustawia dostępne silniki: silniki({"pandoc", "chromium"}); Pillow i ffmpeg z podstawionymi formatami."""
    pil, ff = K.silnik("pillow"), K.silnik("ffmpeg")
    monkeypatch.setitem(pil.__dict__, "_formaty", (PIL_WEJ, PIL_WYJ))
    monkeypatch.setitem(ff.__dict__, "_kodeki", (ENKODERY, DEKODERY))

    def ustaw(dostepne: set[str]):
        for s in K.SILNIKI:
            monkeypatch.setattr(s, "dostepny", (lambda on: lambda: on)(s.nazwa in dostepne))
        monkeypatch.setattr(K, "soffice", lambda: "/usr/bin/soffice" if "libreoffice" in dostepne else None)
        K._graf.cache_clear()
    yield ustaw
    K._graf.cache_clear()


WSZYSTKIE = {"pillow", "ffmpeg", "ghostscript", "pandoc", "chromium"}


# --------------------------------------------------------------------------- rozmiar, strony, nazwy

def test_parse_rozmiar():
    assert K.parse_rozmiar(None) is None
    assert K.parse_rozmiar("1080") == ("dluzszy", 1080)
    assert K.parse_rozmiar("720p") == ("krotszy", 720)
    assert K.parse_rozmiar("50%") == ("proc", 50.0)
    assert K.parse_rozmiar("150%") == ("proc", 100.0)       # nigdy nie powiększa
    assert K.parse_rozmiar("1920 × 1080") == ("pole", 1920, 1080)
    with pytest.raises(K.Blad, match="Zły --rozmiar"):
        K.parse_rozmiar("duży")


def test_nowy_rozmiar_bez_powiekszania():
    assert K.nowy_rozmiar(4000, 3000, ("dluzszy", 1000)) == (1000, 750)
    assert K.nowy_rozmiar(1920, 1080, ("krotszy", 720)) == (1280, 720)
    assert K.nowy_rozmiar(1080, 1920, ("krotszy", 720)) == (720, 1280)       # pionowy film z telefonu
    assert K.nowy_rozmiar(800, 600, ("proc", 50)) == (400, 300)
    assert K.nowy_rozmiar(4000, 1000, ("pole", 1000, 1000)) == (1000, 250)
    assert K.nowy_rozmiar(640, 480, ("dluzszy", 2000)) == (640, 480)          # mniejszy obraz zostaje
    assert K.nowy_rozmiar(640, 480, None) == (640, 480)


def test_skala_ffmpeg():
    assert K.skala_ffmpeg(None) == "scale=trunc(iw/2)*2:trunc(ih/2)*2"         # x264 wymaga parzystych wymiarów
    assert K.skala_ffmpeg(None, parzyste=False) == ""
    s = K.skala_ffmpeg(("krotszy", 720))
    assert "if(gte(iw,ih),-2,trunc((min(720,iw))/2)*2)" in s and s.endswith("flags=lanczos")
    assert "min(480,iw)" in K.skala_ffmpeg(("dluzszy", 480), parzyste=False)
    assert "force_original_aspect_ratio=decrease:force_divisible_by=2" in K.skala_ffmpeg(("pole", 1280, 720))
    assert "iw*0.5" in K.skala_ffmpeg(("proc", 50.0))


def test_strony_lista():
    assert K.strony_lista(None, 10) is None
    assert K.strony_lista("1-3,5,3", 10) == [1, 2, 3, 5]
    assert K.strony_lista("8-", 10) == [8, 9, 10]
    assert K.strony_lista("2-50", 4) == [2, 3, 4]
    with pytest.raises(K.Blad, match="nie wybiera"):
        K.strony_lista("20-", 4)
    with pytest.raises(K.Blad, match="Złe --strony"):
        K.strony_lista("a-b", 4)
    with pytest.raises(K.Blad):
        K.strony_lista("5-2", 10)


def test_wolna_sciezka_nie_nadpisuje(tmp_path):
    p = tmp_path / "a.pdf"
    assert K.wolna_sciezka(p) == p
    p.write_text("x")
    (tmp_path / "a-2.pdf").write_text("x")
    assert K.wolna_sciezka(p) == tmp_path / "a-3.pdf"


def test_format_pliku_i_aliasy():
    assert K.format_pliku(Path("IMG_1.HEIF")) == "heic"
    assert K.format_pliku(Path("a.jpeg")) == "jpg"
    assert K.norm(".Markdown") == "md"
    with pytest.raises(K.Blad, match="Nie znam formatu"):
        K.format_pliku(Path("a.xyz"))
    assert set(K.ALIASY.values()) <= set(K.FORMATY)
    assert {g for g, _, _ in K.FORMATY.values()} == set(K.GRUPY)


def test_cel_sciezka(tmp_path):
    src = tmp_path / "zdjecie.heic"
    assert K.cel_sciezka(src, "jpg", None, None) == tmp_path / "zdjecie.jpg"
    assert K.cel_sciezka(src, "jpg", tmp_path / "out" / "x.png", None) == tmp_path / "out" / "x.jpg"
    assert K.cel_sciezka(src, "jpg", None, tmp_path / "kat") == tmp_path / "kat" / "zdjecie.jpg"
    assert K._baza(Path("krok1-0-umowa-03.png")) == "umowa-03"


# --------------------------------------------------------------------------- trasy

def test_trasy_wielokrokowe(silniki):
    silniki(WSZYSTKIE)
    assert K.trasa("heic", "jpg") == [("heic", "jpg", "pillow")]
    assert K.trasa("md", "pdf") == [("md", "html", "pandoc"), ("html", "pdf", "chromium")]
    assert K.trasa("docx", "pdf") == [("docx", "html", "pandoc"), ("html", "pdf", "chromium")]
    assert K.trasa("md", "png") == [("md", "html", "pandoc"), ("html", "pdf", "chromium"),
                                     ("pdf", "png", "ghostscript")]
    assert K.trasa("svg", "webp") == [("svg", "png", "ffmpeg"), ("png", "webp", "pillow")]
    assert K.trasa("mov", "mp3") == [("mov", "mp3", "ffmpeg")]


def test_trasy_bez_bzdur(silniki):
    silniki(WSZYSTKIE)
    assert K.trasa("png", "txt") is None          # tekst tylko z prawdziwego PDF, nie z obrazu przez PDF
    assert K.trasa("pdf", "txt") == [("pdf", "txt", "ghostscript")]
    assert K.trasa("pdf", "docx") is None         # z PDF nie robimy Worda
    assert K.trasa("mp4", "pdf") is None
    assert K.trasa("jpg", "jpg") is None          # ten sam format bez opcji: nic do zrobienia
    assert K.trasa("jpg", "jpg", K.Opcje(rozmiar="1080")) == [("jpg", "jpg", "pillow")]
    assert K.trasa("pdf", "pdf", K.Opcje(jakosc=40)) == [("pdf", "pdf", "ghostscript")]
    assert all(len(t) <= K.MAX_KROKOW for t in K.trasy("md").values())


def test_libreoffice_wygrywa_i_odblokowuje_arkusze(silniki):
    silniki(WSZYSTKIE)
    assert K.trasa("xlsx", "pdf") is None
    assert "LibreOffice" in K.podpowiedz("xlsx", "pdf")
    assert "tylko inny film" in K.podpowiedz("mp4", "pdf")
    assert "--na txt" in K.podpowiedz("pdf", "docx")
    silniki(WSZYSTKIE | {"libreoffice"})
    assert K.trasa("docx", "pdf") == [("docx", "pdf", "libreoffice")]      # wierniejszy niż pandoc + Chromium
    assert K.trasa("xlsx", "png") == [("xlsx", "pdf", "libreoffice"), ("pdf", "png", "ghostscript")]
    assert K.trasa("csv", "xlsx") == [("csv", "xlsx", "libreoffice")]


def test_bez_silnika_trasa_znika(silniki):
    silniki({"pillow"})
    assert K.trasa("md", "pdf") is None
    assert K.trasa("mp4", "mp3") is None
    assert K.trasa("png", "pdf") == [("png", "pdf", "pillow")]
    fm = K.formaty()
    assert fm["silniki"]["pandoc"] is False and fm["silniki"]["pillow"] is True
    md = next(f for f in fm["formaty"] if f["format"] == "md")
    assert md["odczyt"] is False


def test_cele_pogrupowane(silniki):
    silniki(WSZYSTKIE)
    c = K.cele("mp4")
    grupy = [x["grupa"] for x in c]
    assert grupy == sorted(grupy, key=K.GRUPY.index)
    assert {"mov", "webm", "gif", "mp3", "wav"} <= {x["format"] for x in c}
    assert not {"pdf", "docx", "txt"} & {x["format"] for x in c}
    with pytest.raises(K.Blad):
        K.cele("xyz")


def test_ffmpeg_bez_vp9_i_mp3(silniki, monkeypatch):
    monkeypatch.setitem(K.silnik("ffmpeg").__dict__, "_kodeki", (" A..... aac  AAC\n", ""))
    silniki(WSZYSTKIE)
    assert K.trasa("mp4", "webm") is None and K.trasa("mp4", "mp3") is None
    assert K.trasa("mp4", "m4a") and K.trasa("svg", "png") is None


# --------------------------------------------------------------------------- polecenia silników

def test_ffmpeg_przepakowanie_przed_kodowaniem(silniki):
    silniki(WSZYSTKIE)
    ff = K.silnik("ffmpeg")
    info = {"ok": True, "v": {"codec_name": "h264"}, "a": {"codec_name": "aac"}}
    cmds = ff.polecenia(Path("a.mov"), Path("a.mp4"), "mov", "mp4", K.Opcje(), info)
    assert len(cmds) == 2
    assert "-c" in cmds[0] and cmds[0][cmds[0].index("-c") + 1] == "copy" and "+faststart" in cmds[0]
    assert "libx264" in cmds[1] and cmds[1][cmds[1].index("-crf") + 1] == str(round(35 - 75 * 0.18))
    # rozmiar albo jakość = kodowanie od razu
    cmds = ff.polecenia(Path("a.mov"), Path("a.mp4"), "mov", "mp4", K.Opcje(rozmiar="720p"), info)
    assert len(cmds) == 1 and "min(720,iw)" in cmds[0][cmds[0].index("-vf") + 1]
    # HEVC z iPhone'a nie przechodzi do MP4 przez kopię
    hevc = {"ok": True, "v": {"codec_name": "hevc"}, "a": {"codec_name": "aac"}}
    assert len(ff.polecenia(Path("a.mov"), Path("a.mp4"), "mov", "mp4", K.Opcje(), hevc)) == 1


def test_ffmpeg_hdr_gif_webm_audio(silniki):
    silniki(WSZYSTKIE)
    ff = K.silnik("ffmpeg")
    hdr = {"ok": True, "v": {"codec_name": "h264", "color_transfer": "arib-std-b67"}, "a": {"codec_name": "aac"}}
    cmds = ff.polecenia(Path("a.mov"), Path("a.mp4"), "mov", "mp4", K.Opcje(), hdr)
    assert len(cmds) == 1 and "tonemap=tonemap=mobius" in cmds[0][cmds[0].index("-vf") + 1]
    gif = ff.polecenia(Path("a.mp4"), Path("a.gif"), "mp4", "gif", K.Opcje(), {})[0]
    vf = gif[gif.index("-vf") + 1]
    assert "fps=12" in vf and "min(480,iw)" in vf and "palettegen" in vf and "paletteuse" in vf
    webm = ff.polecenia(Path("a.mp4"), Path("a.webm"), "mp4", "webm", K.Opcje(jakosc=60), {})[0]
    assert "libvpx-vp9" in webm and webm[webm.index("-crf") + 1] == "35" and "libopus" in webm
    mp3 = ff.polecenia(Path("a.mp4"), Path("a.mp3"), "mp4", "mp3", K.Opcje(jakosc=50), {"ok": True, "a": {}})[0]
    assert "-vn" in mp3 and mp3[mp3.index("-b:a") + 1] == "160k"
    assert ff._audio("opus", 100)[-1] == "320k" and ff._audio("m4a", 1)[-1] == "64k"
    with pytest.raises(K.Blad, match="nie ma dźwięku"):
        ff.polecenia(Path("a.mp4"), Path("a.mp3"), "mp4", "mp3", K.Opcje(), {"ok": True, "v": {}, "a": None})


def test_ffmpeg_zly_pierwszy_krok_probuje_kodowania(silniki, monkeypatch, tmp_path):
    silniki(WSZYSTKIE)
    ff = K.silnik("ffmpeg")
    monkeypatch.setattr(ff, "_probe", lambda src: {"ok": True, "v": {"codec_name": "h264"}, "a": {"codec_name": "aac"}})
    wolane = []

    def run(cmd, silnik, timeout, cwd=None):
        wolane.append(cmd)
        Path(cmd[-1]).write_text("x")
        if "copy" in cmd:
            raise K.Blad("FFmpeg: zły kontener")
    monkeypatch.setattr(K, "_run", run)
    dst = tmp_path / "a.mp4"
    assert ff.zamien(tmp_path / "a.mov", dst, "mov", "mp4", K.Opcje(), tmp_path) == [dst]
    assert len(wolane) == 2 and "libx264" in wolane[1]


def test_pandoc_polecenie_bezpieczne(tmp_path):
    p = K.silnik("pandoc")
    (tmp_path / "in").mkdir()
    src, dst = tmp_path / "in" / "umowa.docx", tmp_path / "out" / "umowa.html"
    cmd = p.polecenie(src, dst, "docx", "html", K.Opcje(), tmp_path / "f.lua")
    assert cmd[:5] == ["pandoc", "-f", "docx", "-t", "html5"]
    assert "--lua-filter" in cmd and f"--resource-path={src.parent.resolve()}" in cmd
    assert "--extract-media=umowa-media" in cmd
    assert not any(x.startswith(("--embed-resources", "--self-contained", "--sandbox")) for x in cmd)
    assert cmd[-3:] == ["-o", str(dst.resolve()), str(src.resolve())]
    md = p.polecenie(tmp_path / "a.md", tmp_path / "a.docx", "md", "docx", K.Opcje(), tmp_path / "f.lua")
    assert not any(x.startswith("--extract-media") for x in md)
    assert p.polecenie(tmp_path / "a.txt", tmp_path / "a.html", "txt", "html", K.Opcje(), tmp_path / "f.lua")[2] \
        == "markdown+hard_line_breaks"


def test_filtr_lua_odcina_pliki_z_dysku():
    f = K.FILTR_LUA
    assert 'match("^data:")' in f                     # obrazki wklejone w dokument zostają
    assert "function Image(el)" in f and "RawInline = surowy" in f and "RawBlock = surowy" in f
    assert "%.%." in f and "url%(" in f


def test_serwer_druku_nie_wychodzi_poza_katalog(tmp_path):
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "logo.png").write_bytes(b"x")
    (tmp_path / "tajne.txt").write_text("sekret")
    h = type("H", (K._Zasoby,), {"strona": tmp_path / "doc" / "s.html", "korzenie": ((tmp_path / "doc").resolve(),)})
    tp = K._Zasoby.translate_path
    assert tp(h, "/__strona.html") == str(tmp_path / "doc" / "s.html")
    assert tp(h, "/logo.png") == str((tmp_path / "doc" / "logo.png").resolve())
    assert "__brak__" in tp(h, "/../tajne.txt")
    assert "__brak__" in tp(h, "/%2e%2e/tajne.txt")
    assert "__brak__" in tp(h, "/etc/passwd")


def test_ghostscript_strony_z_numerami(monkeypatch, tmp_path):
    gs = K.silnik("ghostscript")
    monkeypatch.setattr(K, "liczba_stron", lambda pdf: 12)

    def run(cmd, silnik, timeout, cwd=None):
        out = next(x for x in cmd if x.startswith("-sOutputFile=")).split("=", 1)[1]
        assert "-sPageList=2,3,11" in cmd and "-r200" in cmd
        for i in range(1, 4):
            Path(out.replace("%04d", f"{i:04d}")).write_bytes(b"png")
    monkeypatch.setattr(K, "_run", run)
    pliki = gs.zamien(tmp_path / "a.pdf", tmp_path / "a.png", "pdf", "png", K.Opcje(strony="2-3,11", dpi=200), tmp_path)
    assert [p.name for p in pliki] == ["a-02.png", "a-03.png", "a-11.png"]


def test_ghostscript_za_duzo_stron_i_kompresja(monkeypatch, tmp_path):
    gs = K.silnik("ghostscript")
    monkeypatch.setattr(K, "liczba_stron", lambda pdf: 500)
    with pytest.raises(K.Blad, match="500 stron"):
        gs.zamien(tmp_path / "a.pdf", tmp_path / "a.png", "pdf", "png", K.Opcje(), tmp_path)
    wolane = []
    monkeypatch.setattr(K, "_run", lambda cmd, *a, **k: wolane.append(cmd))
    gs.zamien(tmp_path / "a.pdf", tmp_path / "b.pdf", "pdf", "pdf", K.Opcje(jakosc=30), tmp_path)
    assert "-dPDFSETTINGS=/screen" in wolane[0] and "-dSAFER" in wolane[0]


# --------------------------------------------------------------------------- konwersja i CLI

def test_konwertuj_bledy(silniki, tmp_path):
    silniki(WSZYSTKIE)
    src = tmp_path / "a.mp4"
    src.write_bytes(b"x")
    with pytest.raises(K.Blad, match="Nie ma pliku"):
        K.konwertuj(tmp_path / "brak.mp4", "mp3")
    with pytest.raises(K.Blad, match="tylko inny film"):
        K.konwertuj(src, "pdf")
    with pytest.raises(K.Blad, match="już jest w formacie"):
        K.konwertuj(src, "mp4")
    with pytest.raises(K.Blad, match="Nie znam formatu"):
        K.konwertuj(src, "xyz")


def test_konwertuj_wielokrokowo_nie_rusza_zrodla(silniki, monkeypatch, tmp_path):
    silniki(WSZYSTKIE)

    def falszywy(nazwa, stron=1):
        def zamien(src, dst, z, na, opt, tmp):
            if stron == 1:
                dst.write_text(f"{nazwa}:{src.read_text()}")
                return [dst]
            out = [dst.with_name(f"{dst.stem}-{i:02d}{dst.suffix}") for i in range(1, stron + 1)]
            for p in out:
                p.write_text(nazwa)
            return out
        return zamien
    monkeypatch.setattr(K.silnik("pandoc"), "zamien", falszywy("pandoc"))
    monkeypatch.setattr(K.silnik("chromium"), "zamien", falszywy("chromium"))
    monkeypatch.setattr(K.silnik("ghostscript"), "zamien", falszywy("gs", stron=2))
    src = tmp_path / "notatka.md"
    src.write_text("tekst")
    r = K.konwertuj(src, "pdf")
    assert r["pliki"] == [str(tmp_path / "notatka.pdf")] and r["trasa"] == ["md→html (pandoc)", "html→pdf (chromium)"]
    assert (tmp_path / "notatka.pdf").read_text() == "chromium:pandoc:tekst" and src.read_text() == "tekst"
    r = K.konwertuj(src, "png", katalog=tmp_path / "strony")
    assert [Path(p).name for p in r["pliki"]] == ["notatka-01.png", "notatka-02.png"]
    assert K.konwertuj(src, "pdf")["pliki"] == [str(tmp_path / "notatka-2.pdf")]    # istniejący zostaje


def test_cli(silniki, monkeypatch, tmp_path, capsys):
    silniki(WSZYSTKIE)
    a, b = tmp_path / "a.png", tmp_path / "b.txt"
    a.write_bytes(b"x")
    b.write_text("x")
    assert K.main([str(a), "--cele"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["format"] == "png" and "jpg" in [c["format"] for c in out["cele"]]
    assert K.main([str(a), "--na", "jpg", "--jakosc", "0"]) == 1
    assert "--jakosc od 1 do 100" in capsys.readouterr().err
    assert K.main([str(a), str(b), "--na", "jpg", "-o", str(tmp_path / "x.jpg")]) == 1
    assert "-o tylko dla jednego" in capsys.readouterr().err
    monkeypatch.setattr(K.silnik("pillow"), "zamien", lambda s, d, *x: (d.write_bytes(b"jpg"), [d])[1])
    # partia: jeden plik się nie da, drugi tak; błąd w wyniku, nie przerwanie
    assert K.main([str(tmp_path), "--na", "jpg"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [Path(w["pliki"][0]).name for w in out["wyniki"]] == ["a.jpg"] and out["bledy"][0]["plik"].endswith("b.txt")
    assert K.main(["--formaty"]) == 0
    assert "silniki" in json.loads(capsys.readouterr().out)


def test_skill_jest_u_calej_floty():
    import fleetlib as fl
    lock = fl.load_lock()["agents"]
    agenci = [a.name for a in fl.load_fleet().active()]
    for a in agenci:
        wpisy = [x for x in lock.get(a) or [] if x.get("path") == "shared/skills/konwersja-plikow"]
        assert wpisy == [{"source": "jarvo", "path": "shared/skills/konwersja-plikow", "dest": "pliki/konwersja-plikow"}], a


# --------------------------------------------------------------------------- metadane

# wynik `exiftool -j -G1 -a -s -n` dla zdjęcia z iPhone'a (skrót)
IPHONE = {
    "SourceFile": "/x/IMG_2041.jpg", "System:FileName": "IMG_2041.jpg", "System:FileModifyDate": "2026:10:07 10:00:00",
    "File:FileType": "JPEG", "File:Comment": "tajny komentarz", "IFD0:Make": "Apple", "IFD0:Model": "iPhone 15 Pro",
    "IFD0:Orientation": 6, "IFD0:Software": "18.1", "ExifIFD:DateTimeOriginal": "2026:10:05 14:31:00",
    "ExifIFD:OffsetTimeOriginal": "+02:00", "ExifIFD:LensModel": "iPhone 15 Pro back camera", "ExifIFD:ColorSpace": 65535,
    "GPS:GPSLatitude": 50.0614, "GPS:GPSLongitude": 19.9366, "Composite:GPSLatitude": 50.0614,
    "Composite:GPSLongitude": 19.9366, "Composite:GPSPosition": "50.0614 19.9366", "XMP-dc:Description": "Dom przy Rynku",
    "IPTC:Keywords": ["dom", "rynek"], "IFD0:Artist": "Jan Kowalski", "ExifIFD:ImageUniqueID": "ABC123",
    "IFD1:ThumbnailImage": "(Binary data 3170 bytes, use -b option to extract)", "ICC_Profile:DeviceModel": "Apple",
    "ICC_Profile:ProfileDateTime": "2022:01:01 00:00:00", "ExifIFD:UserComment": "",
}
# film po przepakowaniu przez ffmpeg: zerowe daty w nagłówkach to brak daty
CZYSTY_FILM = {"QuickTime:CreateDate": "0000:00:00 00:00:00", "Track1:TrackCreateDate": "0000:00:00 00:00:00",
               "Track1:HandlerDescription": "VideoHandler", "Track1:VendorID": "FFmpeg", "Composite:Rotation": 270}


def test_metadane_kategorie_i_opis():
    kat = K.kategorie(IPHONE)
    assert set(kat) == {"miejsce", "urzadzenie", "czas", "osoba", "opis", "identyfikator", "miniatura"}
    assert "File:Comment" in kat["opis"] and "ExifIFD:UserComment" not in kat["opis"]     # pusty nie liczy się
    assert not any(k.startswith(("System:", "Composite:", "ICC_Profile:")) for v in kat.values() for k in v)
    assert "IFD0:Orientation" not in sum(kat.values(), []) and "ExifIFD:ColorSpace" not in sum(kat.values(), [])
    o = K._opisz(IPHONE)
    assert list(o) == ["miejsce", "urzadzenie", "czas", "osoba", "opis", "identyfikator", "miniatura"]
    assert o["miejsce"]["wartosc"] == "50.0614, 19.9366"
    assert o["urzadzenie"]["wartosc"] == "Apple iPhone 15 Pro"
    assert o["czas"]["wartosc"] == "2026-10-05 14:31"
    assert o["opis"]["wartosc"] == "Dom przy Rynku"           # opis przed słowami kluczowymi
    assert o["osoba"]["wartosc"] == "Jan Kowalski" and o["miniatura"]["wartosc"] == ""
    assert K.kategorie(CZYSTY_FILM) == {}
    aparat = K._opisz({"IFD0:Make": "Canon", "IFD0:Model": "Canon EOS R5", "ID3:Location": "+50.06+019.93/"})
    assert aparat["urzadzenie"]["wartosc"] == "Canon EOS R5" and aparat["miejsce"]["wartosc"] == "+50.06+019.93/"


def test_usun_metadane_polecenia(monkeypatch, tmp_path):
    wolane = []
    monkeypatch.setattr(K, "_run", lambda cmd, *a, **k: wolane.append(cmd))
    K._wyczysc(tmp_path / "a.heic", tmp_path / "b.heic", "heic")
    e = wolane[-1]
    assert e[0] == "exiftool" and "-all=" in e and "-trailer:all=" in e
    assert e[e.index("-tagsFromFile") + 1:e.index("-o")] == ["@", "-ColorSpaceTags", "-Orientation"]   # kolory i obrót zostają
    K._wyczysc(tmp_path / "a.mov", tmp_path / "b.mov", "mov")
    f = wolane[-1]
    assert f[0] == "ffmpeg" and f[f.index("-c") + 1] == "copy" and "0:V" in f and "0:s?" in f
    assert f[f.index("-map_metadata") + 1] == "-1" and "-1" == f[f.index("-map_chapters") + 1] and "+bitexact" in f
    assert "+faststart" in f and f[f.index("-strict") + 1] == "unofficial"
    K._wyczysc(tmp_path / "a.mp3", tmp_path / "b.mp3", "mp3")
    m = wolane[-1]
    assert m[m.index("-map") + 1] == "0:a" and "0:V" not in m and "+faststart" not in m   # bez okładki


def test_usun_metadane_wynik_i_kontrola(monkeypatch, tmp_path):
    src = tmp_path / "IMG_2041.jpg"
    src.write_bytes(b"jpg-z-gps")
    monkeypatch.setattr(K.shutil, "which", lambda n: f"/usr/bin/{n}")
    zostaw = {"IFD0:Orientation": 6, "ExifIFD:ColorSpace": 65535}
    po = [zostaw]
    monkeypatch.setattr(K, "_exiftool_json", lambda p: IPHONE if Path(p) == src else po[0])
    monkeypatch.setattr(K, "_wyczysc", lambda a, b, z: b.write_bytes(b"jpg"))
    r = K.usun_metadane(src)
    out = Path(r["pliki"][0])
    assert out.name == "IMG_2041-bez-metadanych.jpg" and out.read_bytes() == b"jpg" and src.read_bytes() == b"jpg-z-gps"
    assert r["usuniete"]["miejsce"]["wartosc"] == "50.0614, 19.9366" and r["wpisow_usunietych"] == 15   # 17 wpisów, obrót i kolory zostają
    assert r["trasa"] == ["bez metadanych (exiftool)"] and "uwaga" not in r
    assert Path(K.usun_metadane(src, katalog=tmp_path / "out")["pliki"][0]) == tmp_path / "out" / "IMG_2041.jpg"
    # coś zostało po czyszczeniu: błąd i żadnego pliku (zamiast fałszywego „czyste”)
    po[0] = {**zostaw, "GPS:GPSLatitude": 50.06}
    with pytest.raises(K.Blad, match=r"Nie udało się usunąć wszystkiego \(miejsce \(GPS\)\)"):
        K.usun_metadane(src, dst=tmp_path / "x.jpg")
    assert not (tmp_path / "x.jpg").exists()
    # czysty plik: wynik jest, z uwagą
    po[0] = zostaw
    monkeypatch.setattr(K, "_exiftool_json", lambda p: zostaw)
    assert K.usun_metadane(src, dst=tmp_path / "y.jpg")["uwaga"] == "w pliku nie było metadanych do usunięcia"


def test_usun_metadane_bledy(monkeypatch, tmp_path):
    doc, film = tmp_path / "a.doc", tmp_path / "a.mp4"
    doc.write_bytes(b"\xd0\xcf")
    film.write_bytes(b"x")
    with pytest.raises(K.Blad, match=r"nie z DOC\. Zamień go najpierw na DOCX \(--na docx\)"):
        K.usun_metadane(doc)
    monkeypatch.setattr(K.shutil, "which", lambda n: None)
    with pytest.raises(K.Blad, match="wymaga exiftool"):
        K.usun_metadane(film)
    with pytest.raises(K.Blad, match="Odczyt metadanych wymaga exiftool"):
        K.metadane(film)
    with pytest.raises(K.Blad, match="Nie ma pliku"):
        K.usun_metadane(tmp_path / "brak.jpg")


def test_zamiana_filmu_i_dzwieku_bez_metadanych(silniki):
    silniki(WSZYSTKIE)
    ff = K.silnik("ffmpeg")
    info = {"ok": True, "v": {"codec_name": "h264"}, "a": {"codec_name": "aac"}}
    for na, inf in (("mp4", info), ("mp3", info), ("gif", {}), ("webm", {})):
        for cmd in ff.polecenia(Path("a.mov"), Path(f"b.{na}"), "mov", na, K.Opcje(), inf):
            i = cmd.index("-map_metadata")
            assert cmd[i:i + 6] == K.FF_BEZ_METADANYCH, na     # GPS z Androida nie przechodzi do MP4/MP3


def test_zamiana_dopilnowuje_czystosci(monkeypatch, tmp_path):
    p = tmp_path / "a.gif"
    p.write_bytes(b"gif-z-komentarzem")
    stan = {"brudny": True}
    monkeypatch.setattr(K.shutil, "which", lambda n: f"/usr/bin/{n}")
    monkeypatch.setattr(K, "_exiftool_json", lambda f: {"File:Comment": "ul. Długa 5"} if stan["brudny"] else {})

    def czysc(a, b, z):
        b.write_bytes(b"gif")
        stan["brudny"] = False
    monkeypatch.setattr(K, "_wyczysc", czysc)
    K._dopilnuj([p, tmp_path / "a.pdf"])
    assert p.read_bytes() == b"gif" and not list(tmp_path.glob(".*"))


def test_cli_metadane(monkeypatch, tmp_path, capsys):
    a = tmp_path / "a.jpg"
    a.write_bytes(b"x")
    monkeypatch.setattr(K, "metadane", lambda p: {"plik": str(p), "wrazliwe": {}, "czysty": True})
    assert K.main([str(a), "--metadane"]) == 0
    assert json.loads(capsys.readouterr().out)["czysty"] is True
    assert K.main([str(a), "--usun-metadane", "--na", "png"]) == 1
    assert "zostawia format" in capsys.readouterr().err
    monkeypatch.setattr(K, "usun_metadane", lambda p, d, k: {"pliki": [str(d or p)]})
    assert K.main([str(a), "--usun-metadane", "-o", str(tmp_path / "b.jpg")]) == 0
    assert json.loads(capsys.readouterr().out)["pliki"] == [str(tmp_path / "b.jpg")]


# --------------------------------------------------------------------------- prawdziwe narzędzia (obraz Jarva)

def _pil():
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _pil(), reason="brak Pillow")
def test_prawdziwe_zdjecie_bez_gps(tmp_path):
    from PIL import Image
    K._graf.cache_clear()
    src = tmp_path / "zdj.png"
    im = Image.new("RGBA", (400, 200), (255, 0, 0, 128))
    exif = Image.Exif()
    exif[0x8825] = {2: (52.0, 13.0, 0.0)}
    im.save(src, exif=exif)
    r = K.konwertuj(src, "jpg", opt=K.Opcje(rozmiar="100"))
    with Image.open(r["pliki"][0]) as out:
        assert out.format == "JPEG" and out.size == (100, 50) and not out.getexif()
    r = K.konwertuj(src, "ico")
    with Image.open(r["pliki"][0]) as out:
        assert out.format == "ICO"
    K._graf.cache_clear()


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="brak ffmpeg")
def test_prawdziwy_film_na_mp3_i_gif(tmp_path):
    K._graf.cache_clear()
    src = tmp_path / "f.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25:duration=1",
                    "-f", "lavfi", "-i", "sine=duration=1", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(src)],
                   check=True)
    for na in ("mp3", "gif", "mov"):
        r = K.konwertuj(src, na)
        assert Path(r["pliki"][0]).stat().st_size > 0
    K._graf.cache_clear()


@pytest.mark.skipif(not shutil.which("pandoc"), reason="brak pandoc")
def test_prawdziwy_pandoc_nie_wciaga_plikow_z_dysku(tmp_path):
    K._graf.cache_clear()
    tajne = tmp_path / "tajne.txt"
    tajne.write_text("SEKRET-123")
    (tmp_path / "doc").mkdir()
    src = tmp_path / "doc" / "a.md"
    src.write_text(f"# Tytuł\n\n![x]({tajne})\n\n<img src=\"../tajne.txt\">\n\n![y](../tajne.txt)\n", encoding="utf-8")
    for na in ("docx", "epub", "html"):
        r = K.konwertuj(src, na)
        dane = Path(r["pliki"][0]).read_bytes()
        assert b"SEKRET-123" not in dane, na
        if na != "html":
            import zipfile
            with zipfile.ZipFile(r["pliki"][0]) as z:
                assert not any(b"SEKRET-123" in z.read(n) for n in z.namelist()), na
    K._graf.cache_clear()


@pytest.mark.skipif(not (shutil.which("exiftool") and shutil.which("ffmpeg")), reason="brak exiftool albo ffmpeg")
def test_prawdziwe_usuwanie_metadanych(tmp_path):
    K._graf.cache_clear()
    jpg, mov = tmp_path / "zdj.jpg", tmp_path / "film.mov"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x240", "-frames:v", "1", str(jpg)],
                   check=True)
    subprocess.run(["exiftool", "-q", "-overwrite_original", "-Make=Apple", "-Model=iPhone 15 Pro", "-GPSLatitude=50.0614",
                    "-GPSLatitudeRef=N", "-GPSLongitude=19.9366", "-GPSLongitudeRef=E", "-Orientation#=6",
                    "-DateTimeOriginal=2026:10:05 14:31:00", "-Comment=ul. Długa 5", str(jpg)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25:duration=1",
                    "-f", "lavfi", "-i", "sine=duration=1", "-c:v", "libx264", "-c:a", "aac", "-shortest",
                    "-metadata", "location=+50.0614+019.9366/", "-metadata", "creation_time=2026-10-05T12:31:00Z",
                    str(mov)], check=True)
    assert set(K.metadane(jpg)["wrazliwe"]) == {"miejsce", "urzadzenie", "czas", "opis"}
    assert "miejsce" in K.metadane(mov)["wrazliwe"]
    r = K.usun_metadane(jpg)
    out = Path(r["pliki"][0])
    assert K.metadane(out)["czysty"] and out.name == "zdj-bez-metadanych.jpg"
    o = subprocess.run(["exiftool", "-s3", "-n", "-Orientation", str(out)], capture_output=True, text=True).stdout
    assert o.strip() == "6"                                           # obrót zostaje
    assert K.metadane(Path(K.usun_metadane(mov)["pliki"][0]))["czysty"]
    for na in ("mp4", "mp3"):                                         # zamiana też nie przenosi GPS z Androida
        assert K.metadane(Path(K.konwertuj(mov, na)["pliki"][0]))["czysty"], na
    K._graf.cache_clear()


# --------------------------------------------------------------------------- metadane dokumentów

CORE = ('<?xml version="1.0"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/'
        'core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/">'
        '<dc:title>Oferta dla klienta</dc:title><dc:creator>Jan Kowalski</dc:creator>'
        '<cp:lastModifiedBy>Anna Nowak</cp:lastModifiedBy><cp:revision>14</cp:revision>'
        '<dcterms:created>2026-10-05T14:31:00Z</dcterms:created></cp:coreProperties>')
APP = ('<?xml version="1.0"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
       '<Template>Normal.dotm</Template><TotalTime>95</TotalTime><Pages>2</Pages><Application>Microsoft Office Word'
       '</Application><Company>Kowalski Sp. z o.o.</Company></Properties>')
CUSTOM = ('<?xml version="1.0"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" '
          'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><property name="Klient" '
          'pid="2"><vt:lpwstr>Bank X</vt:lpwstr></property></Properties>')
TRESC = b'<w:document><w:body><w:p><w:ins w:author="Anna Nowak"><w:r><w:t>nowe</w:t></w:r></w:ins></w:p></w:body></w:document>'


def _docx(p: Path, czesci: dict) -> Path:
    import zipfile
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        for nazwa, dane in czesci.items():
            z.writestr(zipfile.ZipInfo(nazwa, date_time=(2026, 10, 5, 14, 31, 0)), dane)
        z.comment = b"Jan K."
    return p


def test_pakiet_odczyt_kategorie_i_uwagi(tmp_path):
    d = _docx(tmp_path / "oferta.docx", {"[Content_Types].xml": "<Types/>", "word/document.xml": TRESC,
                                        "word/comments.xml": '<w:comments><w:comment w:author="Anna">x</w:comment></w:comments>', "docProps/core.xml": CORE,
                                        "docProps/app.xml": APP, "docProps/custom.xml": CUSTOM})
    tagi = K._pakiet_json(d)
    assert tagi["XML:Creator"] == "Jan Kowalski" and tagi["XML:TotalEditTime"] == "95" and tagi["Custom:Klient"] == "Bank X"
    o = K._opisz(tagi)
    assert list(o) == ["czas", "firma", "historia", "osoba", "opis", "wlasne"]
    assert o["firma"]["wartosc"] == "Kowalski Sp. z o.o." and o["osoba"]["wartosc"] == "Jan Kowalski"
    assert o["czas"]["wartosc"] == "2026-10-05 14:31" and o["wlasne"]["wartosc"] == "Klient"
    assert o["historia"]["wpisy"] == 2 and o["opis"]["wpisy"] == 2      # tytuł i komentarz ZIP-a
    assert "XML:Pages" not in sum(K.kategorie(tagi).values(), [])         # liczba stron to nie dane o człowieku
    m = K.metadane(d)
    assert m["format"] == "docx" and not m["czysty"]
    assert m["uwagi"] == ["komentarze z nazwiskami autorów", "śledzone zmiany z nazwiskami autorów"]


def test_pakiet_odt_meta(tmp_path):
    meta = ('<?xml version="1.0"?><office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" office:version="1.3"><office:meta>'
            '<meta:initial-creator>Jan Kowalski</meta:initial-creator><dc:date>2026-10-05T14:31:00</dc:date>'
            '<meta:generator>LibreOffice/24.2</meta:generator><meta:editing-cycles>3</meta:editing-cycles>'
            '<meta:template xlink:href="Firma.ott"/><meta:user-defined meta:name="Projekt">Alfa</meta:user-defined>'
            '<meta:document-statistic meta:page-count="1"/></office:meta></office:document-meta>')
    d = _docx(tmp_path / "a.odt", {"mimetype": "application/vnd.oasis.opendocument.text", "meta.xml": meta,
                                   "content.xml": "<office:document-content><office:annotation>x</office:annotation>"
                                                  "</office:document-content>"})
    tagi = K._pakiet_json(d)
    assert tagi["XML:InitialCreator"] == "Jan Kowalski" and tagi["XML:Template"] == "Firma.ott"
    assert set(K._opisz(tagi)) == {"czas", "firma", "historia", "osoba", "opis", "wlasne"}
    assert K.metadane(d)["uwagi"] == ["komentarze z nazwiskami autorów"]
    out = tmp_path / "czysty.odt"
    K._wyczysc_pakiet(d, out)
    import zipfile
    with zipfile.ZipFile(out) as z, zipfile.ZipFile(d) as zrodlo:
        assert z.namelist()[0] == "mimetype"                               # ODF: mimetype pierwszy, bez kompresji
        assert z.getinfo("mimetype").compress_type == zrodlo.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert b'office:version="1.3"' in z.read("meta.xml")
    assert K._pakiet_json(out) == {}


def test_usun_metadane_docx_bez_exiftoola(monkeypatch, tmp_path):
    import zipfile
    monkeypatch.setattr(K.shutil, "which", lambda n: None)          # pakiety nie potrzebują exiftoola
    d = _docx(tmp_path / "oferta.docx", {"word/document.xml": TRESC, "word/comments.xml": "<w:comments/>",
                                        "docProps/core.xml": CORE,
                                        "docProps/app.xml": APP, "docProps/custom.xml": CUSTOM,
                                        "word/media/logo.png": b"\x89PNG" + bytes(range(256))})
    r = K.usun_metadane(d)
    out = Path(r["pliki"][0])
    assert out.name == "oferta-bez-metadanych.docx" and r["trasa"] == ["bez metadanych (Jarvo (XML w pliku))"]
    assert set(r["usuniete"]) == {"czas", "firma", "historia", "osoba", "opis", "wlasne"}   # pusty comments.xml: bez uwagi
    assert r["uwagi"] == ["zostało w treści: śledzone zmiany z nazwiskami autorów (usuń je w edytorze, jeśli plik "
                          "idzie do kogoś)"]
    with zipfile.ZipFile(d) as a, zipfile.ZipFile(out) as b:
        assert a.namelist() == b.namelist() and not b.comment
        assert all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in b.infolist())
        assert b.read("word/media/logo.png") == a.read("word/media/logo.png") and b.read("word/document.xml") == TRESC
        for czesc in ("docProps/core.xml", "docProps/app.xml", "docProps/custom.xml"):
            assert b.read(czesc).decode() == K.PUSTE_XML[czesc]
    assert K.metadane(out)["czysty"]
    # zepsuty dokument: błąd po polsku, nie wyjątek zipfile
    (tmp_path / "zly.docx").write_bytes(b"to nie zip")
    with pytest.raises(K.Blad, match="Uszkodzony dokument"):
        K.metadane(tmp_path / "zly.docx")


def test_pdf_metadane_kategorie_i_polecenia(monkeypatch, tmp_path):
    pdf = {"PDF:Author": "Jan Kowalski", "PDF:Creator": "Microsoft Word", "PDF:Producer": "macOS Quartz",
           "PDF:CreateDate": "2026:10:05 14:31:00", "PDF:PageCount": 2, "XMP-xmp:CreatorTool": "Word",
           "XMP-xmpMM:DocumentID": "uuid:1", "PDF:Title": "Oferta"}
    kat = K.kategorie(pdf)
    assert kat["firma"] == ["PDF:Creator", "PDF:Producer", "XMP-xmp:CreatorTool"] and kat["osoba"] == ["PDF:Author"]
    assert "PDF:PageCount" not in sum(kat.values(), [])
    assert K.kategorie({"QuickTime:Producer": "Studio"}) == {"osoba": ["QuickTime:Producer"]}   # w filmie to osoba
    wolane = []
    monkeypatch.setattr(K, "_run", lambda cmd, *a, **k: wolane.append(cmd))
    K._wyczysc(tmp_path / "a.pdf", tmp_path / "b.pdf", "pdf")
    assert wolane[0][0] == "exiftool" and "-all:all=" in wolane[0]
    assert wolane[1][:2] == ["qpdf", "--deterministic-id"] and wolane[1][-1] == str(tmp_path / "b.pdf")
    assert wolane[1][2] == wolane[0][wolane[0].index("-o") + 1]           # qpdf przepisuje wynik exiftoola


def test_pdf_zabezpieczony_haslem(monkeypatch, tmp_path):
    pdf = tmp_path / "umowa.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(K.shutil, "which", lambda n: f"/usr/bin/{n}")
    monkeypatch.setattr(K.subprocess, "run", lambda cmd, **k: subprocess.CompletedProcess(cmd, 0))
    with pytest.raises(K.Blad, match="zabezpieczony hasłem"):
        K.usun_metadane(pdf)
