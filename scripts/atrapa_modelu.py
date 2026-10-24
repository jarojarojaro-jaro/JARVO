#!/usr/bin/env python3
"""Atrapa modelu: serwer zgodny z OpenAI Chat Completions do testów aplikacji Jarvo bez klucza dostawcy.

Odpowiada przewidywalnie, strumieniem (SSE) albo jednym JSON-em, więc przez prawdziwego Hermesa da się sprawdzić
całą drogę wiadomości: strumień tekstu, wywołanie narzędzia i wynik, błąd modelu, zatrzymanie w trakcie.
Tylko do testów (piaskownica, CI): nie ma w obrazie żadnego profilu, który by z niej korzystał.

    python3 scripts/atrapa_modelu.py --port 9199          # http://127.0.0.1:9199/v1
    python3 scripts/atrapa_modelu.py --port 9199 --dziennik /tmp/jarvo-e2e/atrapa.jsonl
                                                          # każde ciało zapytania jako jedna linia JSON (test E2E)
                                                          # z adresem zapytania w polu „_sciezka”

Ścieżka przed /chat/completions jest dowolna, więc każdy profil testu może mieć własny adres
(`base_url: http://127.0.0.1:9197/p/<profil>/v1`), a dziennik pokazuje, do którego profilu poszła tura.

Polecenia w treści ostatniej wiadomości właściciela (w nawiasach kwadratowych, reszta tekstu wraca w odpowiedzi):
    [narzedzie:NAZWA {"arg": 1}]   wywołaj narzędzie NAZWA z argumentami (JSON); po wyniku krótkie podsumowanie
    [wolno]                        strumień po słowie co 0,4 s (test „Zatrzymaj”)
    [wolno:<s>]                    strumień rozłożony na <s> sekund (test Stop, dopisz, wznowienia strumienia);
                                   z [narzedzie:…] dotyczy odpowiedzi po wyniku narzędzia (tura trwa dłużej)
    [plik:<ścieżka>]               linia „Plik: <ścieżka>” w odpowiedzi (karta pliku); można kilka
    [blad]                         HTTP 500 od „dostawcy”
    [dlugo]                        długa odpowiedź z nagłówkami, listą, tabelą i kodem (test renderowania)

Gotowe odpowiedzi (zrzuty ekranu z prawdziwą treścią zamiast echa): `--odpowiedzi PLIK.json` z mapą
{"fragment wiadomości właściciela": "odpowiedź (Markdown)"}; pierwsza wiadomość, która zawiera fragment, dostaje tę
odpowiedź (z `[wolno:<s>]` też strumieniem). Reszta działa jak wyżej.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

POLECENIE_NARZEDZIA = re.compile(r"\[narzedzie:([A-Za-z0-9_.-]+)\s*(\{.*?\})?\]", re.S)
POLECENIE_WOLNO = re.compile(r"\[wolno(?::(\d+(?:[.,]\d+)?))?\]")
POLECENIE_PLIK = re.compile(r"\[plik:([^\]\n]+)\]")
POLECENIE = re.compile(r"\[[a-z]+(?::[^\]\n]*)?\]")      # do wycięcia z echa: [wolno], [wolno:5], [plik:/x]
WOLNO_MAKS = 600.0
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


GOTOWE: dict[str, str] = {}          # --odpowiedzi: fragment wiadomości właściciela → odpowiedź


def odpowiedz(wiadomosci: list[dict], model: str) -> dict:
    """Co atrapa „powie”: {'tekst': str} albo {'narzedzie': (nazwa, argumenty)}; także {'blad': True},
    {'wolno': True} (z `[wolno:<s>]` dodatkowo {'wolno_s': s}: cały strumień trwa s sekund)."""
    ostatnia = wiadomosci[-1] if wiadomosci else {}
    tekst = next((_tekst(w.get("content")) for w in reversed(wiadomosci) if w.get("role") == "user"), "")
    if ostatnia.get("role") == "tool":
        wynik = _tekst(ostatnia.get("content"))[:300]
        return _wolno({"tekst": f"Narzędzie zwróciło: {wynik}", "wolno": False}, tekst)
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
    gotowa = next((v for k, v in GOTOWE.items() if k and k in tekst), None)
    if gotowa is not None:
        return _wolno({"tekst": gotowa, "wolno": False}, tekst)
    czysty = POLECENIE.sub("", tekst).strip()
    odp = f"Atrapa ({model}): {czysty[:400] or 'gotowe.'}"
    for sciezka in POLECENIE_PLIK.findall(tekst):
        odp += f"\nPlik: {sciezka.strip()}"
    return _wolno({"tekst": odp, "wolno": False}, tekst)


def _wolno(plan: dict[str, Any], tekst: str) -> dict[str, Any]:
    """`[wolno]` / `[wolno:<s>]` z wiadomości właściciela: tempo odpowiedzi (także tej po wyniku narzędzia)."""
    w = POLECENIE_WOLNO.search(tekst)
    if w:
        plan["wolno"] = True
        if w.group(1):
            plan["wolno_s"] = min(WOLNO_MAKS, float(w.group(1).replace(",", ".")))
    return plan


def kawalki(plan: dict) -> tuple[list[str], float]:
    """Kawałki strumienia i pauza po każdym. `[wolno:<s>]`: razem s sekund, co najmniej 2 kawałki na sekundę,
    gdy tekst na to pozwala (krótkie echo idzie wtedy po znaku, a dwukropek razem ze znakiem przed nim: kawałek
    zaczęty od „:” Hermes trzyma do końca linii jako możliwy komentarz SSE); `[wolno]`: po słowie co 0,4 s;
    inaczej 0,02 s."""
    tekst = plan.get("tekst") or ""
    slowa = re.findall(r"\S+\s*|\s+", tekst)
    if plan.get("wolno_s"):
        s = float(plan["wolno_s"])
        czesci = slowa if len(slowa) >= s * 2 else re.findall(r".:*", tekst, re.S)
        return czesci, s / max(1, len(czesci))
    return slowa, (0.4 if plan.get("wolno") else 0.02)


class Obsluga(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    dziennik: str | None = None          # --dziennik: plik JSONL z ciałami zapytań
    _zamek = threading.Lock()

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
        self._zapisz(zapytanie, self.path)
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

    def _zapisz(self, zapytanie: Any, sciezka: str = "") -> None:
        """Jedna linia JSON na zapytanie (plik 0600 na POSIX, dopisywany pod zamkiem: serwer jest wielowątkowy);
        ciało z polem `_sciezka` = adres zapytania (profil testu po `base_url`)."""
        if not self.dziennik:
            return
        wpis = {**zapytanie, "_sciezka": sciezka} if isinstance(zapytanie, dict) else zapytanie
        linia = json.dumps(wpis, ensure_ascii=False) + "\n"
        with self._zamek:
            fd = os.open(self.dziennik, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as f:
                f.write(linia)

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
                czesci, pauza = kawalki(plan)
                for czesc in czesci:
                    wyslij({"content": czesc})
                    time.sleep(pauza)
                wyslij({}, "stop")
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):    # klient przerwał (Zatrzymaj): nic więcej nie wysyłamy
            pass
        self.close_connection = True


class Serwer(ThreadingHTTPServer):
    """ThreadingHTTPServer bez odwrotnego DNS przy starcie: HTTPServer.server_bind woła socket.getfqdn między bind
    a listen, przy wolnym DNS to sekundy, a port przez ten czas nie przyjmuje połączeń. Nazwy serwera atrapa
    nie używa."""

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = str(self.server_address[0]), self.server_address[1]


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
    ap.add_argument("--dziennik", metavar="PLIK", help="dopisuj każde ciało zapytania jako jedną linię JSON")
    ap.add_argument("--odpowiedzi", metavar="PLIK", help="JSON {fragment wiadomości: gotowa odpowiedź} (zrzuty ekranu)")
    a = ap.parse_args()
    Obsluga.dziennik = a.dziennik
    if a.odpowiedzi:
        with open(a.odpowiedzi, encoding="utf-8") as f:
            dane = json.load(f)
        GOTOWE.update({str(k): str(v) for k, v in dane.items()} if isinstance(dane, dict) else {})
    Serwer((a.host, a.port), Obsluga).serve_forever()


if __name__ == "__main__":
    main()
