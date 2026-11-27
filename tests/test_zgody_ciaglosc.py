"""Ciągłość tury: samo rozumowanie modelu w trakcie pracy nie kończy zadania (zgody/plugin/ciaglosc.py, 27.11 T1 i C1)."""
import importlib.util
import os
import subprocess
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("jarvo_ciaglosc", REPO / "zgody" / "plugin" / "ciaglosc.py")
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)


class Agent:
    def _extract_reasoning(self, m):
        return m.reasoning


def hermes_finish(agent, *, assistant_message, finish_reason, messages, **_):
    """Jak Hermes: przy pustej treści i stop awansuje rozumowanie, inaczej (pusto) idzie drabiną pustej odpowiedzi."""
    awans = agent._extract_reasoning(assistant_message) if finish_reason == "stop" and not assistant_message.content else None
    return "koniec: " + awans if awans else ("drabina" if not assistant_message.content else assistant_message.content)


def msg(content=None, reasoning="myślę, co dalej", tool_calls=None):
    return types.SimpleNamespace(content=content, reasoning=reasoning, tool_calls=tool_calls)


PRACA = [{"role": "user", "content": "zrób"}, {"role": "assistant", "tool_calls": [1]}, {"role": "tool", "content": "ok"}]
ROZMOWA = [{"role": "user", "content": "cześć"}]


def test_w_trakcie_pracy_samo_rozumowanie_idzie_dalej():
    f = c.owin(hermes_finish)
    agent = Agent()
    assert f(agent, assistant_message=msg(), finish_reason="stop", messages=PRACA) == "drabina"
    assert agent._extract_reasoning(msg()) == "myślę, co dalej"           # przywrócone po wywołaniu


def test_rozmowa_bez_narzedzi_i_zwykla_odpowiedz_bez_zmian():
    f = c.owin(hermes_finish)
    assert f(Agent(), assistant_message=msg(), finish_reason="stop", messages=ROZMOWA) == "koniec: myślę, co dalej"
    assert f(Agent(), assistant_message=msg("Gotowe."), finish_reason="stop", messages=PRACA) == "Gotowe."
    assert f(Agent(), assistant_message=msg(), finish_reason="length", messages=PRACA) == "drabina"
    assert c.owin(f) is f                                                   # bez podwójnego owinięcia


@pytest.mark.skipif(not os.environ.get("JARVO_HERMES_PYTHON"), reason="bez Pythona Hermesa (JARVO_HERMES_PYTHON)")
def test_owija_petle_prawdziwego_hermesa():
    kod = ("import importlib.util,sys; s=importlib.util.spec_from_file_location('c', sys.argv[1]); m=importlib.util."
           "module_from_spec(s); s.loader.exec_module(m); assert m.zarejestruj(); from agent import conversation_loop "
           "as cl; assert getattr(cl.finish_text_response, m.ZNACZNIK); print('ok')")
    wynik = subprocess.run([os.environ["JARVO_HERMES_PYTHON"], "-c", kod, str(REPO / "zgody" / "plugin" / "ciaglosc.py")],
                           capture_output=True, text=True, cwd=os.environ.get("JARVO_TEST_HERMES_SRC") or None, timeout=120)
    assert wynik.stdout.strip() == "ok", wynik.stderr[-2000:]
