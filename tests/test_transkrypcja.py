"""Wspólny skill transkrypcja-filmu: link albo plik → tekst mowy (napisy platformy albo Parakeet)."""

from __future__ import annotations

import json
import os

from conftest import load_script

T = load_script("shared/skills/transkrypcja-filmu/scripts/transkrybuj.py")

AUTO_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000 align:start position:0%
Hey<00:00:00.500><c> Claude,</c><00:00:01.000><c> my</c>

00:00:02.000 --> 00:00:02.010 align:start position:0%
Hey Claude, my

00:00:02.010 --> 00:00:04.000 align:start position:0%
Hey Claude, my
website<00:00:03.000><c> looks</c><00:00:03.500><c> like</c><00:00:03.600><c> trash</c>

01:02:03.000 --> 01:02:04.000
koniec
"""


def test_auto_captions_are_deduplicated_and_timed():
    seg = T.vtt_srt_na_segmenty(AUTO_VTT)
    assert [s["tekst"] for s in seg] == ["Hey Claude, my", "website looks like trash", "koniec"]
    assert [s["od"] for s in seg] == [0, 2, 3723]
    assert T.czas(3723) == "01:02:03" and T.czas(75) == "01:15"


def test_local_file_goes_straight_to_speech(tmp_path, monkeypatch):
    """Plik lokalny: bez yt-dlp, od razu Parakeet; wynik to sam tekst (bez analizy obrazu)."""
    b = tmp_path / "bin"
    b.mkdir()
    (b / "jarvo-stt").write_text('#!/usr/bin/env bash\nprintf "1\\n00:00:00,000 --> 00:00:02,500\\n'
                                 'Make no mistakes.\\n" > "$3"\n', encoding="utf-8")
    (b / "jarvo-stt").chmod(0o755)
    monkeypatch.setenv("PATH", f"{b}:{os.environ['PATH']}")
    film = tmp_path / "film.mp4"
    film.write_bytes(b"\0")
    out = tmp_path / "out"
    assert T.main([str(film), "-o", str(out)]) == 0
    w = json.loads((out / "transkrypcja.json").read_text(encoding="utf-8"))
    assert w["mowa"] == [{"od": 0, "tekst": "Make no mistakes."}]
    assert w["mowa_zrodlo"].startswith("rozpoznanie mowy") and "ekran" not in w
    md = (out / "transkrypcja.md").read_text(encoding="utf-8")
    assert "[00:00] Make no mistakes." in md and "Pełny tekst" in md


def test_platform_captions_skip_download(tmp_path, monkeypatch):
    """Link z napisami: tekst z napisów platformy, dźwięku nie pobieramy."""
    monkeypatch.setattr(T, "metadane", lambda url: {"tytul": "Film", "autor": "a", "dlugosc_s": 30,
                                                    "url": url, "platforma": "Youtube"})
    monkeypatch.setattr(T, "napisy", lambda url, tmp: ([{"od": 0, "tekst": "Cześć"}], "pl"))
    monkeypatch.setattr(T, "pobierz_dzwiek", lambda *a: (_ for _ in ()).throw(AssertionError("pobrano dźwięk")))
    out = tmp_path / "out"
    assert T.main(["https://youtu.be/abc", "-o", str(out)]) == 0
    assert "Tekst z: napisy z platformy (pl)" in (out / "transkrypcja.md").read_text(encoding="utf-8")


def test_bad_input_and_too_long_video(tmp_path, monkeypatch):
    assert T.main(["nie-ma-takiego-pliku.mp4", "-o", str(tmp_path / "o")]) == 2
    monkeypatch.setattr(T, "metadane", lambda url: {"tytul": "x", "autor": None, "dlugosc_s": 3 * 3600,
                                                    "url": url, "platforma": "Youtube"})
    assert T.main(["https://youtu.be/abc", "-o", str(tmp_path / "o")]) == 2


def test_bot_check_gives_clear_message(monkeypatch):
    import subprocess
    import pytest
    monkeypatch.setattr(T, "narzedzie", lambda n: n)
    monkeypatch.setattr(T, "uruchom", lambda cmd: subprocess.CompletedProcess(
        cmd, 1, "", "ERROR: [youtube] x: Sign in to confirm you’re not a bot. Use --cookies-from-browser"))
    with pytest.raises(SystemExit, match="poproś o plik"):
        T.metadane("https://youtu.be/x")
