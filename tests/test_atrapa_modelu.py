"""Atrapa modelu (scripts/atrapa_modelu.py): przewidywalne odpowiedzi i zgodność z OpenAI Chat Completions."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import atrapa_modelu as am  # noqa: E402


def test_odpowiedz_echo_i_polskie_znaki():
    plan = am.odpowiedz([{"role": "user", "content": "zażółć gęślą jaźń"}], "atrapa")
    assert plan["tekst"] == "Atrapa (atrapa): zażółć gęślą jaźń"
    assert not plan.get("wolno")


def test_odpowiedz_narzedzie_i_wynik():
    plan = am.odpowiedz([{"role": "user", "content": 'zrób [narzedzie:rozmowa {"agent": "web"}]'}], "m")
    assert plan["narzedzie"] == ("rozmowa", {"agent": "web"})
    po = am.odpowiedz([{"role": "user", "content": "x"}, {"role": "tool", "content": "ok: przekazane"}], "m")
    assert po["tekst"].startswith("Narzędzie zwróciło: ok: przekazane")
    assert not po.get("wolno")
    wolno = am.odpowiedz([{"role": "user", "content": '[narzedzie:terminal {"command": "rm -rf /tmp/x"}] [wolno:12]'},
                          {"role": "tool", "content": "denied"}], "m")
    assert wolno["tekst"] == "Narzędzie zwróciło: denied" and wolno["wolno_s"] == 12.0


def test_odpowiedz_polecenia_specjalne():
    assert am.odpowiedz([{"role": "user", "content": "[blad]"}], "m") == {"blad": True}
    assert am.odpowiedz([{"role": "user", "content": "a [wolno]"}], "m")["wolno"] is True
    assert "| Sekcja | Stan |" in am.odpowiedz([{"role": "user", "content": "[dlugo]"}], "m")["tekst"]
    tresc = [{"type": "text", "text": "z obrazem"}, {"type": "image_url", "image_url": {"url": "data:,"}}]
    assert am.odpowiedz([{"role": "user", "content": tresc}], "m")["tekst"].endswith("z obrazem")


def test_gotowe_odpowiedzi_z_pliku(monkeypatch):
    monkeypatch.setattr(am, "GOTOWE", {"plan strony": "## Plan\n\n1. Start"})
    w = [{"role": "user", "content": "Kontekst…\n\nZrób plan strony dla piekarni [wolno:2]"}]
    plan = am.odpowiedz(w, "m")
    assert plan["tekst"] == "## Plan\n\n1. Start" and plan["wolno_s"] == 2
    assert am.odpowiedz([{"role": "user", "content": "co innego"}], "m")["tekst"].startswith("Atrapa (m)")


def test_wolno_z_czasem_i_plik():
    plan = am.odpowiedz([{"role": "user", "content": "raport [wolno:5] [plik:/opt/data/jarvo/a b.html] [plik:/tmp/c.pdf]"}], "m")
    assert plan["tekst"] == "Atrapa (m): raport\nPlik: /opt/data/jarvo/a b.html\nPlik: /tmp/c.pdf"
    assert plan["wolno"] is True and plan["wolno_s"] == 5.0
    czesci, pauza = am.kawalki(plan)
    assert "".join(czesci) == plan["tekst"] and len(czesci) >= 10
    assert abs(pauza * len(czesci) - 5.0) < 1e-9
    assert am.odpowiedz([{"role": "user", "content": "x [wolno:2,5]"}], "m")["wolno_s"] == 2.5
    assert am.odpowiedz([{"role": "user", "content": "x [wolno:99999]"}], "m")["wolno_s"] == am.WOLNO_MAKS
    # po znaku, ale żaden kawałek nie zaczyna się od „:” (Hermes trzymałby go do końca linii jak komentarz SSE)
    krotkie, _ = am.kawalki(am.odpowiedz([{"role": "user", "content": "[wolno:15] raz dwa"}], "atrapa"))
    assert "".join(krotkie) == "Atrapa (atrapa): raz dwa" and "):" in krotkie
    assert not any(k.startswith(":") for k in krotkie) and len(krotkie) == len("Atrapa (atrapa): raz dwa") - 1
    zwykle = am.odpowiedz([{"role": "user", "content": "x [wolno]"}], "m")
    assert "wolno_s" not in zwykle and am.kawalki(zwykle)[1] == 0.4
    assert am.kawalki(am.odpowiedz([{"role": "user", "content": "x"}], "m"))[1] == 0.02


def _wolny_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def serwer(tmp_path):
    """Atrapa w osobnym procesie; gotowa, gdy odpowie na GET /models (pełne zapytanie, nie samo połączenie TCP).
    Proces, który padł albo nie wstał w 30 s, kończy test komunikatem zamiast przekroczenia czasu w zapytaniu."""
    port = _wolny_port()
    p = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "atrapa_modelu.py"), "--port", str(port),
                          "--dziennik", str(tmp_path / "atrapa.jsonl")])
    adres = f"http://127.0.0.1:{port}/v1"
    koniec = time.monotonic() + 30
    while True:
        try:
            with urllib.request.urlopen(adres + "/models", timeout=2):
                break
        except OSError:                                  # także URLError: jeszcze nie słucha
            if p.poll() is not None or time.monotonic() > koniec:
                p.kill()
                p.wait(timeout=5)
                pytest.fail(f"atrapa modelu nie wstała na porcie {port} (kod {p.returncode})")
            time.sleep(0.1)
    yield adres
    p.terminate()
    p.wait(timeout=5)


def _post(url: str, dane: dict) -> bytes:
    zap = urllib.request.Request(url, json.dumps(dane).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(zap, timeout=5) as o:
        return o.read()


def test_serwer_strumien_narzedzie_i_blad(serwer):
    with urllib.request.urlopen(serwer + "/models", timeout=5) as o:
        assert json.load(o)["data"][0]["id"] == "atrapa"
    surowe = _post(serwer + "/chat/completions", {"model": "atrapa", "stream": True,
                                                  "messages": [{"role": "user", "content": "cześć świecie"}]}).decode()
    kawalki = [json.loads(l[6:]) for l in surowe.splitlines() if l.startswith("data: {")]
    assert "".join(k["choices"][0]["delta"].get("content", "") for k in kawalki) == "Atrapa (atrapa): cześć świecie"
    assert kawalki[-1]["choices"][0]["finish_reason"] == "stop" and surowe.rstrip().endswith("data: [DONE]")
    cala = json.loads(_post(serwer + "/chat/completions", {"model": "m", "messages": [
        {"role": "user", "content": '[narzedzie:todo {"a": 1}]'}]}))
    wyw = cala["choices"][0]["message"]["tool_calls"][0]
    assert cala["choices"][0]["finish_reason"] == "tool_calls" and wyw["function"]["name"] == "todo"
    assert json.loads(wyw["function"]["arguments"]) == {"a": 1}
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(serwer + "/chat/completions", {"model": "m", "messages": [{"role": "user", "content": "[blad]"}]})
    assert e.value.code == 500


def test_serwer_wolno_dziennik_i_plik(serwer, tmp_path):
    zapytania = [
        {"model": "atrapa", "stream": True, "messages": [{"role": "user", "content": "zażółć [wolno:1] [plik:/opt/data/x.png]"}]},
        {"model": "m", "messages": [{"role": "user", "content": "drugie"}]},
    ]
    start = time.monotonic()
    surowe = _post(serwer + "/chat/completions", zapytania[0]).decode()
    assert time.monotonic() - start >= 0.9
    kawalki = [json.loads(l[6:]) for l in surowe.splitlines() if l.startswith("data: {")]
    tekst = "".join(k["choices"][0]["delta"].get("content", "") for k in kawalki)
    assert tekst == "Atrapa (atrapa): zażółć\nPlik: /opt/data/x.png"
    # dowolna ścieżka przed /chat/completions (base_url profilu testu): dziennik zapisuje ją w _sciezka
    _post(serwer.replace("/v1", "/p/test-e2e-j/v1") + "/chat/completions", zapytania[1])
    dziennik = tmp_path / "atrapa.jsonl"
    linie = dziennik.read_text(encoding="utf-8").splitlines()
    wpisy = [json.loads(l) for l in linie]
    assert [{k: v for k, v in w.items() if k != "_sciezka"} for w in wpisy] == zapytania
    assert [w["_sciezka"] for w in wpisy] == ["/v1/chat/completions", "/p/test-e2e-j/v1/chat/completions"]
    assert "zażółć" in linie[0]                       # bez ucieczek \uXXXX: grep po polsku działa
    if os.name != "nt":                               # tryb pliku chroni tylko na POSIX (Windows: os.open go pomija)
        assert dziennik.stat().st_mode & 0o777 == 0o600
