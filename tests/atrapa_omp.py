"""Atrapa programu `omp` dla testów sesji omp (tests/test_sesje_omp.py, tests/test_omp_sesje.py).

Zachowanie z plików w katalogu `ATRAPA_OMP` (tworzy je `zrob`): `argv.jsonl` (każde wywołanie), `held.json` (lista
trzymanych sesji dla `session lease`), `tryb` (ok | blad | spi). Tura `-p --mode json` wypisuje zdarzenia jak omp
18.22: nagłówek sesji, przyrosty tekstu, narzędzie z argumentami i wynikiem (z napisem SEKRET, którego nie wolno
przepuścić dalej), `message_end`, `agent_end`.
"""
from __future__ import annotations

from pathlib import Path

import atrapy

KOD = r'''
import json, os, sys, time
from pathlib import Path
k = Path(os.environ["ATRAPA_OMP"])
a = sys.argv[1:]
with (k / "argv.jsonl").open("a") as f:
    f.write(json.dumps(a) + "\n")
if a[:2] == ["session", "lease"]:
    ids = a[a.index("--") + 1:]
    held = json.loads((k / "held.json").read_text()) if (k / "held.json").exists() else []
    print(json.dumps({"held": [i for i in ids if i in held], "unknown": []}))
    sys.exit(0)
if "-p" not in a:
    sys.exit(int((k / "kod_terminala").read_text()) if (k / "kod_terminala").exists() else 0)
tryb = (k / "tryb").read_text().strip() if (k / "tryb").exists() else "ok"
def e(**z):
    print(json.dumps(z), flush=True)
e(type="session", version=3, id="s1", timestamp="t", cwd=os.getcwd())
e(type="agent_start")
if tryb == "blad":
    print("model niedostępny", file=sys.stderr)
    sys.exit(1)
e(type="tool_execution_start", toolCallId="c1", toolName="bash", intent="Sprawdzam GPU", args={"command": "cat SEKRET"})
e(type="tool_execution_end", toolCallId="c1", toolName="bash", isError=False, result={"content": [{"type": "text", "text": "SEKRET"}]})
if tryb == "spi":
    (k / "spi").write_text(str(os.getpid()))
    time.sleep(60)
for d in ("Gotowe", ", zrobione."):
    e(type="message_update", assistantMessageEvent={"type": "text_delta", "contentIndex": 0, "delta": d})
    e(type="message_update", assistantMessageEvent={"type": "toolcall_delta", "contentIndex": 1, "delta": "SEKRET"})
e(type="message_end", message={"role": "toolResult", "content": [{"type": "text", "text": "SEKRET"}]})
e(type="message_end", message={"role": "assistant", "content": [{"type": "text", "text": "Gotowe, zrobione."}]})
e(type="agent_end", messages=[], isTerminal=True)
'''


def zrob(katalog: Path) -> Path:
    katalog.mkdir(parents=True, exist_ok=True)
    return atrapy.program(katalog, "omp", KOD)
