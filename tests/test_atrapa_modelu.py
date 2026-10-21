"""Atrapa modelu (scripts/atrapa_modelu.py): przewidywalne odpowiedzi i zgodność z OpenAI Chat Completions."""
import json
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


def test_odpowiedz_polecenia_specjalne():
    assert am.odpowiedz([{"role": "user", "content": "[blad]"}], "m") == {"blad": True}
    assert am.odpowiedz([{"role": "user", "content": "a [wolno]"}], "m")["wolno"] is True
    assert "| Sekcja | Stan |" in am.odpowiedz([{"role": "user", "content": "[dlugo]"}], "m")["tekst"]
    tresc = [{"type": "text", "text": "z obrazem"}, {"type": "image_url", "image_url": {"url": "data:,"}}]
    assert am.odpowiedz([{"role": "user", "content": tresc}], "m")["tekst"].endswith("z obrazem")


def _wolny_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def serwer():
    port = _wolny_port()
    p = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "atrapa_modelu.py"), "--port", str(port)])
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
            break
        except OSError:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}/v1"
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
