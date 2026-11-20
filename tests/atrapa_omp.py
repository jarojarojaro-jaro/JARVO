"""Atrapa programu `omp` dla testów sesji omp (tests/test_sesje_omp.py, tests/test_omp_sesje.py, test_centrum_silnik).

Zachowanie z plików w katalogu `ATRAPA_OMP` (tworzy je `zrob`): `argv.jsonl` (każde wywołanie), `held.json` (lista
trzymanych sesji dla `session lease`), `kod_terminala` (kod wyjścia terminalu), `tryb` (czytany przy każdym prompcie).

`--mode rpc` mówi protokołem JSONL jak omp 19 (omp://rpc.md): ramka `ready`, komendy ze stdin do `rpc.jsonl` (obrazy
jako liczba), odpowiedzi `response` z `id`. Tura (`prompt`) w osobnym wątku, więc komendy (steer, abort) działają
w jej trakcie: `agent_start`, wiadomość użytkownika, narzędzie z argumentami i wynikiem (z napisem SEKRET, którego
nie wolno przepuścić dalej), przyrosty tekstu, `message_end` asystenta z `usage`, `agent_end`, `prompt_result`,
`session_settled`. Steer w trakcie tury: `queue_update`, a w punkcie dostarczenia `message_end` użytkownika ze
`steering: true` (odpowiedź mówi wtedy „Dopiski: N.”); steer bez tury rusza turę sam (jak omp). Udana tura dopisuje
do pliku sesji `<session-dir>/2026_<sesja>.jsonl` (format v3: nagłówek, wiadomości użytkownika, wywołanie narzędzia,
wynik z SEKRET, odpowiedź z modelem i zużyciem). Prompt ze znacznikiem `[plan]` daje odpowiedź z planem
i `[[czeka-na-tak]]`. `compact` daje `tokensBefore` 5000 i kontekst 1200 (plik `compact_blad` = odmowa omp).

Tryby: ok | blad (prompt_result z błędem modelu) | spi (tura czeka na abort do 60 s, plik `spi`) | czekaj (tura
czeka na steer do 30 s, plik `czeka`, potem go dostarcza) | nie_dostarczaj (jak czekaj, ale steer zostaje
w kolejce) | padnij (proces kończy się w trakcie tury kodem 3). Tryby poza ok i blad działają na jedną turę (plik
`tryb` znika), następna tura jest zwykła.
"""
from __future__ import annotations

from pathlib import Path

import atrapy

KOD = r'''
import datetime, json, os, sys, threading, time, uuid
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
if not ("--mode" in a and a[a.index("--mode") + 1] == "rpc"):
    sys.exit(int((k / "kod_terminala").read_text()) if (k / "kod_terminala").exists() else 0)

zamek = threading.Lock()
stan = {"kolejka": [], "abort": threading.Event(), "tura": None, "odpowiedzi": 0, "kontekst": 5000}


def e(**z):
    with zamek:
        print(json.dumps(z), flush=True)


def tryb():
    return (k / "tryb").read_text().strip() if (k / "tryb").exists() else "ok"


def zapisz_sesje(wiadomosci_uzytkownika, odp):
    if "--session-dir" not in a or "--resume" not in a:
        return
    sd, sid = Path(a[a.index("--session-dir") + 1]), a[a.index("--resume") + 1]
    plik, lisc = sd / f"2026_{sid}.jsonl", k / f"lisc_{sid}"
    rodzic = lisc.read_text() if lisc.exists() else None
    teraz = datetime.datetime.now(datetime.timezone.utc).isoformat()
    linie = [] if plik.exists() else [dict(type="session", version=3, id=sid, timestamp=teraz, cwd=os.getcwd())]
    wpisy = [("user", [{"type": "text", "text": t}]) for t in wiadomosci_uzytkownika]
    wpisy += [("assistant", [{"type": "toolCall", "id": "c1", "name": "bash", "intent": "Sprawdzam GPU",
                              "arguments": {"command": "cat SEKRET"}}]),
              ("toolResult", [{"type": "text", "text": "SEKRET"}]),
              ("assistant", [{"type": "text", "text": odp}])]
    for rola, tresc in wpisy:
        i = uuid.uuid4().hex[:8]
        wiad = dict(role=rola, content=tresc, **({"toolCallId": "c1", "toolName": "bash"} if rola == "toolResult" else {}))
        if rola == "assistant" and tresc[0]["type"] == "text":
            wiad.update(provider="atrapa", model="model-x",
                        usage={"input": 100, "output": 10, "cacheRead": 900, "cacheWrite": 50, "cost": {"total": 0.01}})
        linie.append(dict(type="message", id=i, parentId=rodzic, timestamp=teraz, message=wiad))
        rodzic = i
    sd.mkdir(parents=True, exist_ok=True)
    with plik.open("a") as f:
        for z in linie:
            f.write(json.dumps(z, ensure_ascii=False) + "\n")
    lisc.write_text(rodzic)


def dostarcz(dopiski):
    while stan["kolejka"]:
        s = stan["kolejka"].pop(0)
        e(type="queue_update", steering=list(stan["kolejka"]), followUp=[])
        e(type="message_end", message={"role": "user", "content": [{"type": "text", "text": s}], "steering": True})
        dopiski.append(s)


def koniec(id_, status, **reszta):
    e(type="agent_end", messages=[], isTerminal=True, yielded=True)
    if id_:
        e(type="prompt_result", id=id_, agentInvoked=True, status=status, sessionSettled=True, **reszta)
    e(type="session_settled")
    stan["tura"] = None


def tura(id_, prompt):
    t = tryb()
    if t not in ("ok", "blad"):
        (k / "tryb").unlink()
    stan["abort"].clear()
    e(type="agent_start")
    dopiski = []
    if prompt is not None:
        e(type="message_end", message={"role": "user", "content": [{"type": "text", "text": prompt}]})
    else:
        dostarcz(dopiski)
    if t == "blad":
        print("model niedostępny", file=sys.stderr, flush=True)
        return koniec(id_, "error", error={"message": "model niedostępny", "retryable": False})
    if t == "padnij":
        print("omp padł", file=sys.stderr, flush=True)
        os._exit(3)
    e(type="tool_execution_start", toolCallId="c1", toolName="bash", intent="Sprawdzam GPU", args={"command": "cat SEKRET"})
    e(type="tool_execution_end", toolCallId="c1", toolName="bash", isError=False, result={"content": [{"type": "text", "text": "SEKRET"}]})
    if t == "spi":
        (k / "spi").write_text(str(os.getpid()))
        stan["abort"].wait(60)
    if t in ("czekaj", "nie_dostarczaj"):
        (k / "czeka").write_text(str(os.getpid()))
        for _ in range(300):
            if stan["kolejka"] or stan["abort"].is_set():
                break
            time.sleep(0.1)
    if stan["abort"].is_set():
        return koniec(id_, "aborted")
    if t != "nie_dostarczaj":
        dostarcz(dopiski)
    for d in ("Gotowe", ", zrobione."):
        e(type="message_update", assistantMessageEvent={"type": "text_delta", "contentIndex": 0, "delta": d})
        e(type="message_update", assistantMessageEvent={"type": "toolcall_delta", "contentIndex": 1, "delta": "SEKRET"})
    e(type="message_end", message={"role": "toolResult", "content": [{"type": "text", "text": "SEKRET"}]})
    odp = "Plan: restart bramy. [[czeka-na-tak]]" if "[plan]" in (prompt or "") else "Gotowe, zrobione."
    if dopiski:
        odp += f" Dopiski: {len(dopiski)}."
    stan["odpowiedzi"] += 1
    stan["kontekst"] = 5000
    e(type="message_end", message={"role": "assistant", "content": [{"type": "text", "text": odp}], "provider": "atrapa",
                                   "model": "model-x", "usage": {"input": 100, "output": 10, "cacheRead": 900,
                                                                 "cacheWrite": 50, "cost": {"total": 0.01}}})
    zapisz_sesje(([prompt] if prompt is not None else []) + dopiski, odp)
    koniec(id_, "completed")


def odpowiedz(c, sukces=True, **reszta):
    e(id=c.get("id"), type="response", command=c.get("type"), success=sukces, **reszta)


def statystyki():
    n = stan["odpowiedzi"]
    return {"tokens": {"input": 100 * n, "output": 10 * n, "cacheRead": 900 * n, "cacheWrite": 50 * n},
            "cost": 0.01 * n, "contextUsage": {"tokens": stan["kontekst"], "contextWindow": 200000,
                                               "percent": stan["kontekst"] / 2000}}


e(type="ready", protocolVersion=1, supportedProtocolVersions=[1, 2], maxFrameBytes=1048576)
for linia in sys.stdin:
    try:
        c = json.loads(linia)
    except ValueError:
        continue
    zapis = {**c, **({"images": len(c["images"])} if "images" in c else {})}
    with (k / "rpc.jsonl").open("a") as f:
        f.write(json.dumps(zapis, ensure_ascii=False) + "\n")
    typ = c.get("type")
    if typ == "get_state":
        odpowiedz(c, data={"model": {"provider": "atrapa", "id": "model-x", "contextWindow": 200000},
                           "isStreaming": stan["tura"] is not None, "thinkingLevel": stan.get("myslenie", "medium"),
                           "fastModeEnabled": stan.get("fast", False)})
    elif typ == "set_thinking_level":
        stan["myslenie"] = c.get("level")
        odpowiedz(c)
    elif typ == "set_fast_mode":
        stan["fast"] = bool(c.get("enabled"))
        odpowiedz(c)
    elif typ == "get_session_stats":
        odpowiedz(c, data=statystyki())
    elif typ == "prompt":
        odpowiedz(c)
        stan["tura"] = threading.Thread(target=tura, args=(c.get("id"), c.get("message")))
        stan["tura"].start()
    elif typ == "steer":
        stan["kolejka"].append(c.get("message"))
        e(type="queue_update", steering=list(stan["kolejka"]), followUp=[])
        odpowiedz(c)
        if stan["tura"] is None:
            stan["tura"] = threading.Thread(target=tura, args=(None, None))
            stan["tura"].start()
    elif typ == "remove_queued_message":
        jest = c.get("message") in stan["kolejka"]
        if jest:
            stan["kolejka"].remove(c.get("message"))
            e(type="queue_update", steering=list(stan["kolejka"]), followUp=[])
        odpowiedz(c, data={"removed": jest})
    elif typ in ("abort", "abort_and_restore_queue"):
        zwrot = [{"text": s} for s in stan["kolejka"]]
        stan["kolejka"].clear()
        stan["abort"].set()
        odpowiedz(c, data={"steering": zwrot, "followUp": []} if typ == "abort_and_restore_queue" else None)
    elif typ == "compact":
        if (k / "compact_blad").exists():
            e(type="manual_compaction_start")
            e(type="manual_compaction_end", aborted=False, skipped=True, errorMessage="Nothing to compact (session too small)")
            odpowiedz(c, False, error="Nothing to compact (session too small)")
        else:
            e(type="manual_compaction_start")
            stan["kontekst"] = 1200
            wynik = {"summary": "streszczenie", "firstKeptEntryId": "x", "tokensBefore": 5000, "details": {}}
            e(type="manual_compaction_end", aborted=False, result=wynik)
            odpowiedz(c, data=wynik)
    elif typ == "extension_ui_response":
        pass
    else:
        odpowiedz(c, False, error=f"Unknown command: {typ}")
t = stan["tura"]
if t is not None:
    t.join()
'''


def zrob(katalog: Path) -> Path:
    katalog.mkdir(parents=True, exist_ok=True)
    return atrapy.program(katalog, "omp", KOD)
