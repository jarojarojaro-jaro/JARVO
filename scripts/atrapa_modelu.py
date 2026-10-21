#!/usr/bin/env python3
"""Atrapa modelu: serwer zgodny z OpenAI Chat Completions do testów aplikacji Jarvo bez klucza dostawcy.

Odpowiada przewidywalnie, strumieniem (SSE) albo jednym JSON-em, więc przez prawdziwego Hermesa da się sprawdzić
całą drogę wiadomości: strumień tekstu, wywołanie narzędzia i wynik, błąd modelu, zatrzymanie w trakcie.
Tylko do testów (piaskownica, CI): nie ma w obrazie żadnego profilu, który by z niej korzystał.

    python3 scripts/atrapa_modelu.py --port 9199          # http://127.0.0.1:9199/v1

Polecenia w treści ostatniej wiadomości właściciela (w nawiasach kwadratowych, reszta tekstu wraca w odpowiedzi):
    [narzedzie:NAZWA {"arg": 1}]   wywołaj narzędzie NAZWA z argumentami (JSON); po wyniku krótkie podsumowanie
    [wolno]                        strumień po słowie co 0,4 s (test „Zatrzymaj”)
    [blad]                         HTTP 500 od „dostawcy”
    [dlugo]                        długa odpowiedź z nagłówkami, listą, tabelą i kodem (test renderowania)
"""
from __future__ import annotations

import argparse
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

POLECENIE_NARZEDZIA = re.compile(r"\[narzedzie:([A-Za-z0-9_.-]+)\s*(\{.*?\})?\]", re.S)
DLUGI_TEKST = """## Plan strony

Zrobię to w trzech krokach:

1. **Treść** — nagłówek, oferta, godziny otwarcia.
2. **Wygląd** — kolory z logo, zdjęcia chleba.
3. **Publikacja** — podgląd, potem domena.

| Sekcja | Stan |
|---|---|
| Oferta | gotowe |
| Kontakt | w toku |

```html
<h1>Piekarnia Złoty Kłos</h1>
```

Daj znać, czy zaczynamy."""


def _tekst(tresc: Any) -> str:
    if isinstance(tresc, str):
        return tresc
    if isinstance(tresc, list):
        return " ".join(str(c.get("text", "")) for c in tresc if isinstance(c, dict) and c.get("type") in ("text", "input_text"))
    return ""


def odpowiedz(wiadomosci: list[dict], model: str) -> dict:
    """Co atrapa „powie”: {'tekst': str} albo {'narzedzie': (nazwa, argumenty)}; także {'blad': True}, {'wolno': True}."""
    ostatnia = wiadomosci[-1] if wiadomosci else {}
    if ostatnia.get("role") == "tool":
        wynik = _tekst(ostatnia.get("content"))[:300]
        return {"tekst": f"Narzędzie zwróciło: {wynik}"}
    tekst = next((_tekst(w.get("content")) for w in reversed(wiadomosci) if w.get("role") == "user"), "")
    if "[blad]" in tekst:
        return {"blad": True}
    m = POLECENIE_NARZEDZIA.search(tekst)
    if m:
        try:
            argumenty = json.loads(m.group(2) or "{}")
        except ValueError:
            argumenty = {}
        return {"narzedzie": (m.group(1), argumenty)}
    if "[dlugo]" in tekst:
        return {"tekst": DLUGI_TEKST}
    czysty = re.sub(r"\[[a-z]+\]", "", tekst).strip()
    return {"tekst": f"Atrapa ({model}): {czysty[:400] or 'gotowe.'}", "wolno": "[wolno]" in tekst}


class Obsluga(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_: Any) -> None:    # cicho: testy czytają tylko odpowiedzi
        pass

    def _json(self, kod: int, dane: dict) -> None:
        cialo = json.dumps(dane, ensure_ascii=False).encode()
        self.send_response(kod)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cialo)))
        self.end_headers()
        self.wfile.write(cialo)

    def do_GET(self) -> None:
        if self.path.rstrip("/").endswith("/models"):
            self._json(200, {"object": "list", "data": [{"id": "atrapa", "object": "model", "owned_by": "jarvo"}]})
        else:
            self._json(404, {"error": {"message": "nie ma"}})

    def do_POST(self) -> None:
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self._json(404, {"error": {"message": "nie ma"}})
            return
        dlugosc = int(self.headers.get("Content-Length") or 0)
        try:
            zapytanie = json.loads(self.rfile.read(dlugosc) or b"{}")
        except ValueError:
            self._json(400, {"error": {"message": "zły JSON"}})
            return
        model = str(zapytanie.get("model") or "atrapa")
        plan = odpowiedz(zapytanie.get("messages") or [], model)
        if plan.get("blad"):
            self._json(500, {"error": {"message": "atrapa: celowy błąd dostawcy", "type": "server_error"}})
            return
        ident = f"atrapa-{time.monotonic_ns()}"
        if zapytanie.get("stream"):
            self._strumien(ident, model, plan)
        else:
            self._json(200, _cala(ident, model, plan))

    def _strumien(self, ident: str, model: str, plan: dict) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        def wyslij(delta: dict, koniec: str | None = None) -> None:
            kawalek = {"id": ident, "object": "chat.completion.chunk", "created": int(time.time()), "model": model,
                       "choices": [{"index": 0, "delta": delta, "finish_reason": koniec}]}
            self.wfile.write(f"data: {json.dumps(kawalek, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()

        try:
            wyslij({"role": "assistant"})
            if "narzedzie" in plan:
                nazwa, argumenty = plan["narzedzie"]
                wyslij({"tool_calls": [{"index": 0, "id": f"call_{ident[-8:]}", "type": "function",
                                        "function": {"name": nazwa, "arguments": json.dumps(argumenty, ensure_ascii=False)}}]})
                wyslij({}, "tool_calls")
            else:
                pauza = 0.4 if plan.get("wolno") else 0.02
                for slowo in re.findall(r"\S+\s*|\s+", plan["tekst"]):
                    wyslij({"content": slowo})
                    time.sleep(pauza)
                wyslij({}, "stop")
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):    # klient przerwał (Zatrzymaj): nic więcej nie wysyłamy
            pass
        self.close_connection = True


def _cala(ident: str, model: str, plan: dict) -> dict:
    wiadomosc: dict[str, Any] = {"role": "assistant", "content": plan.get("tekst")}
    koniec = "stop"
    if "narzedzie" in plan:
        nazwa, argumenty = plan["narzedzie"]
        wiadomosc = {"role": "assistant", "content": None, "tool_calls": [{
            "id": f"call_{ident[-8:]}", "type": "function",
            "function": {"name": nazwa, "arguments": json.dumps(argumenty, ensure_ascii=False)}}]}
        koniec = "tool_calls"
    return {"id": ident, "object": "chat.completion", "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "message": wiadomosc, "finish_reason": koniec}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}}


def main() -> None:
    ap = argparse.ArgumentParser(description="Atrapa modelu zgodna z OpenAI (tylko testy)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9199)
    a = ap.parse_args()
    ThreadingHTTPServer((a.host, a.port), Obsluga).serve_forever()


if __name__ == "__main__":
    main()
