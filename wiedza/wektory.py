#!/usr/bin/env python3
"""Usługa wektorów skarbca wiedzy: jeden ciepły model multilingual-e5-small na instalację (docs/WIEDZA.md §7, W4).

    python wektory.py serwuj --model <katalog e5-small> --stan <state> [--skarbiec <knowledge>] [--watki 4] [--port 0]
    python wektory.py sprawdz --model <katalog e5-small> [--watki 2] ["zdanie" …]

Działa w venvie narzędzi (numpy, onnxruntime, tokenizers z locka `narzedzia`) jako usługa nadzorcy `wektory`
(jarvo/nadzorca.py, Windows, macOS, Linux). Brama Hermesa i `jarvo chat` nie mają tych bibliotek, więc wtyczka
jarvo-wiedza, kompilacja i `wiedza.py` pytają usługę (wiedza.KlientWektorow): HTTP tylko na 127.0.0.1, port wybrany
przez system, token z `secrets` w nagłówku `Authorization: Bearer`; port, token, id modelu i PID usługa zapisuje przy
starcie w `<state>/wektory.json` (tylko właściciel pliku, zapis atomowy) i usuwa przy zatrzymaniu. Bez tokenu odpowiedź
401; treści zapytań nie trafiają do logu.

  GET  /zdrowie   {"model", "wymiar", "pid", "od"}
  POST /osadz     {"teksty": [...]} → {"model", "wymiar", "wektory": base64 float32 little-endian, wiersz na tekst}

Osadzanie jak w pomiarze (2026-11-07): teksty z prefiksami e5 („query: ”, „passage: ”; dokłada je klient), do 512
tokenów, średnia ukrytych stanów po tokenach z maską, normalizacja L2; onnxruntime na CPU z `--watki` wątkami (4),
na Windows bez zdarzeń telemetrii. Id modelu: `multilingual-e5-small@<rewizja>` ze znacznika instalatora
(.jarvo-model.json, jarvo/modele.py), a bez niego z sumy pliku modelu; inny id = pełne przeliczenie wektorów.
Z `--skarbiec` usługa po starcie nadrabia brakujące wektory skarbca (Indeks.odswiez_wektory w osobnym wątku): zasiew
przy instalacji biegnie, zanim usługa wstanie.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import http.server
import importlib.util
import json
import os
import secrets
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Callable

_HERE = Path(__file__).resolve().parent

NAZWA = "multilingual-e5-small"
PLIK_MODELU = "model_quantized.onnx"
PLIK_TOKENIZERA = "tokenizer.json"
ZNACZNIK = ".jarvo-model.json"         # jarvo/modele.py: rewizja i sumy plików z manifestu
MAX_TOKENOW = 512
WATKI = 4
MAX_TEKSTOW = 64                       # na jedno zapytanie
MAX_ZNAKOW_TEKSTU = 8000               # dłuższy tekst i tak przytnie tokenizer (512 tokenów)
MAX_ZAPYTANIA_B = 2 << 20


def _lib():
    """wiedza.py obok (stała WEKTORY_STAN, zamien_plik, Indeks do nadrabiania); ten sam moduł co we wtyczce."""
    mod = sys.modules.get("jarvo_wiedza_lib")
    if mod is not None:
        return mod
    spec = importlib.util.spec_from_file_location("jarvo_wiedza_lib", _HERE / "wiedza.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["jarvo_wiedza_lib"] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop("jarvo_wiedza_lib", None)
        raise
    return mod


def model_id(katalog: Path) -> str:
    """`multilingual-e5-small@<12 znaków rewizji>` ze znacznika instalatora, a bez znacznika (kopia ręczna) z sha256
    pliku modelu."""
    try:
        rewizja = str(json.loads((Path(katalog) / ZNACZNIK).read_text(encoding="utf-8")).get("rewizja") or "")
    except (OSError, ValueError, AttributeError):
        rewizja = ""
    if rewizja:
        return f"{NAZWA}@{rewizja[:12]}"
    h = hashlib.sha256()
    with open(Path(katalog) / PLIK_MODELU, "rb") as f:
        for kawalek in iter(lambda: f.read(1 << 20), b""):
            h.update(kawalek)
    return f"{NAZWA}@sha256-{h.hexdigest()[:12]}"


class ModelE5:
    """multilingual-e5-small w ONNX (Xenova, int8) z tokenizerem HF: wywołanie = bajty float32 little-endian
    znormalizowanych wektorów, wiersz na tekst."""

    def __init__(self, katalog: Path, watki: int = WATKI):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        try:
            ort.disable_telemetry_events()          # koło Windows: dostawca ETW Microsoft.ML.ONNXRuntime
        except Exception:  # noqa: BLE001  (starsze API: model i tak działa)
            pass
        katalog = Path(katalog)
        self.np = np
        opcje = ort.SessionOptions()
        opcje.intra_op_num_threads = max(1, int(watki))
        opcje.inter_op_num_threads = 1
        opcje.enable_cpu_mem_arena = False      # bez areny pamięć po dużej paczce wraca (zmierzone: 0,55 zamiast 0,62 GB)
        self.sesja = ort.InferenceSession(str(katalog / PLIK_MODELU), opcje, providers=["CPUExecutionProvider"])
        self.wejscia = {i.name for i in self.sesja.get_inputs()}
        self.tok = Tokenizer.from_file(str(katalog / PLIK_TOKENIZERA))
        self.tok.enable_truncation(MAX_TOKENOW)
        self.tok.enable_padding()
        self.id = model_id(katalog)
        self.wymiar = len(self(["query: test"])) // 4

    def __call__(self, teksty: list[str]) -> bytes:
        np = self.np
        enc = self.tok.encode_batch(list(teksty))
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        maska = np.array([e.attention_mask for e in enc], dtype=np.int64)
        wej = {"input_ids": ids, "attention_mask": maska}
        if "token_type_ids" in self.wejscia:
            wej["token_type_ids"] = np.zeros_like(ids)
        ukryte = self.sesja.run(None, wej)[0]                           # [teksty, tokeny, wymiar]
        m = maska[..., None].astype(np.float32)
        v = (ukryte * m).sum(1) / np.clip(m.sum(1), 1e-9, None)         # średnia po tokenach z maską
        v = v / np.clip(np.linalg.norm(v, axis=1, keepdims=True), 1e-12, None)
        return np.ascontiguousarray(v, dtype="<f4").tobytes()


class _Obsluga(http.server.BaseHTTPRequestHandler):
    server_version = "jarvo-wektory/1"
    sys_version = ""

    def log_message(self, format: str, *args) -> None:     # noqa: A002  bez adresów i treści zapytań w logu
        pass

    def _odpowiedz(self, kod: int, dane: dict) -> None:
        tresc = json.dumps(dane, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(tresc)))
        self.end_headers()
        self.wfile.write(tresc)

    def _wpuszczony(self) -> bool:
        if hmac.compare_digest(self.headers.get("Authorization", "").encode("utf-8", "replace"),
                               f"Bearer {self.server.token}".encode("utf-8")):
            return True
        self._odpowiedz(401, {"blad": "brak tokenu"})
        return False

    def do_GET(self) -> None:                                  # noqa: N802
        if not self._wpuszczony():
            return
        if self.path != "/zdrowie":
            self._odpowiedz(404, {"blad": "nieznana ścieżka"})
            return
        s = self.server
        self._odpowiedz(200, {"model": s.model, "wymiar": s.wymiar, "pid": os.getpid(), "od": s.od})

    def do_POST(self) -> None:                                 # noqa: N802
        if not self._wpuszczony():
            return
        if self.path != "/osadz":
            self._odpowiedz(404, {"blad": "nieznana ścieżka"})
            return
        try:
            dlugosc = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            dlugosc = -1
        if not 0 < dlugosc <= MAX_ZAPYTANIA_B:
            self._odpowiedz(413, {"blad": f"zapytanie od 1 B do {MAX_ZAPYTANIA_B} B"})
            return
        try:
            teksty = json.loads(self.rfile.read(dlugosc).decode("utf-8")).get("teksty")
        except (ValueError, AttributeError):
            teksty = None
        if not isinstance(teksty, list) or not 0 < len(teksty) <= MAX_TEKSTOW or not all(isinstance(t, str) for t in teksty):
            self._odpowiedz(400, {"blad": f'{{"teksty": [napisy]}}, od 1 do {MAX_TEKSTOW}'})
            return
        try:
            bajty = self.server.koder([t[:MAX_ZNAKOW_TEKSTU] for t in teksty])
        except Exception as e:  # noqa: BLE001  błąd modelu: 500 dla tego zapytania, usługa działa dalej
            self.server.log(f"wektory: błąd osadzania: {type(e).__name__}: {e}"[:300])
            self._odpowiedz(500, {"blad": "błąd modelu"})
            return
        self._odpowiedz(200, {"model": self.server.model, "wymiar": self.server.wymiar,
                              "wektory": base64.b64encode(bajty).decode("ascii")})


class SerwerWektorow(http.server.ThreadingHTTPServer):
    """Serwer HTTP na 127.0.0.1 (port 0 = wybiera system). `koder(teksty) -> bajty float32` to ModelE5 albo atrapa
    w testach; `zamknij()` usuwa state/wektory.json, jeśli nadal opisuje ten serwer."""

    daemon_threads = True

    def __init__(self, koder: Callable[[list[str]], bytes], model: str, wymiar: int, stan: str | Path, *, port: int = 0,
                 log: Callable[[str], None] = print):
        super().__init__(("127.0.0.1", port), _Obsluga)
        self.koder, self.model, self.wymiar, self.log = koder, model, int(wymiar), log
        self.token = secrets.token_urlsafe(32)
        self.od = round(time.time(), 1)
        self.stan = Path(stan)
        self.plik = self.stan / _lib().WEKTORY_STAN
        self._zapisz_stan()

    def _zapisz_stan(self) -> None:
        self.stan.mkdir(parents=True, exist_ok=True)
        tmp = self.plik.with_name(f"{self.plik.name}.{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)     # token: tylko właściciel pliku (POSIX)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"port": self.server_address[1], "token": self.token, "model": self.model, "wymiar": self.wymiar,
                       "pid": os.getpid(), "od": self.od}, f)
        _lib().zamien_plik(tmp, self.plik)

    def handle_error(self, request, client_address) -> None:
        """Klient zrezygnował (przekroczony czas przypomnienia, 0,3 s): zwykła rzecz, bez śladu w logu. Inny błąd:
        jedna linia z typem, bez treści zapytania."""
        blad = sys.exc_info()[1]
        if isinstance(blad, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError)):
            return
        self.log(f"wektory: błąd obsługi zapytania: {type(blad).__name__}")

    def zamknij(self) -> None:
        self.server_close()
        try:
            if json.loads(self.plik.read_text(encoding="utf-8")).get("token") == self.token:
                self.plik.unlink()
        except (OSError, ValueError, AttributeError):
            pass


class OsadzanieLokalne:
    """Ten sam interfejs co wiedza.KlientWektorow (`model`, `osadz`), ale bez HTTP: nadrabianie wektorów w usłudze."""

    def __init__(self, koder: Callable[[list[str]], bytes], model: str, wymiar: int):
        self.koder, self.model, self.wymiar = koder, model, int(wymiar)

    def osadz(self, teksty: list[str], czas_s: float | None = None):
        if not teksty:
            return []
        plaskie = _lib().wektor_z_bajtow(self.koder(list(teksty)))
        return [plaskie[i * self.wymiar:(i + 1) * self.wymiar] for i in range(len(teksty))]


def nadrob(skarbiec: str | Path, stan: str | Path, osadzacz, log: Callable[[str], None] = print) -> dict | None:
    """Brakujące i nieaktualne wektory skarbca (po indeksie FTS); None, gdy skarbca nie ma."""
    lib = _lib()
    sk = lib.Skarbiec(skarbiec, stan)
    if not sk.root.is_dir():
        log(f"wektory: brak skarbca {sk.root}, nadrabianie pominięte")
        return None
    ix = lib.Indeks(sk)
    try:
        ix.odswiez()
        w = ix.odswiez_wektory(osadzacz)
    finally:
        ix.zamknij()
    log(lib.opis_wektorow(w))
    return w


def serwuj(a) -> int:
    log = lambda s: print(s, flush=True)                                      # noqa: E731  stdout → <logi>/wektory.log
    start = time.perf_counter()
    model = ModelE5(Path(a.model), a.watki)
    serwer = SerwerWektorow(model, model.id, model.wymiar, a.stan, port=a.port, log=log)
    log(f"wektory: {model.id} (wymiar {model.wymiar}, wątki {a.watki}) gotowy w {time.perf_counter() - start:.1f} s, "
        f"port {serwer.server_address[1]}")

    def zatrzymaj(*_a) -> None:
        threading.Thread(target=serwer.shutdown, daemon=True).start()        # shutdown() czeka na pętlę: inny wątek

    signal.signal(signal.SIGTERM, zatrzymaj)
    if hasattr(signal, "SIGBREAK"):                                           # Windows: Ctrl+Break od nadzorcy
        signal.signal(signal.SIGBREAK, zatrzymaj)
    if a.skarbiec:
        def watek() -> None:
            try:
                nadrob(a.skarbiec, a.stan, OsadzanieLokalne(model, model.id, model.wymiar), log)
            except Exception as e:  # noqa: BLE001  usługa działa dalej, wektory dorobi indeksuj albo kompilacja
                log(f"wektory: nadrabianie nieudane: {type(e).__name__}: {e}"[:300])
        threading.Thread(target=watek, name="wektory-nadrabianie", daemon=True).start()
    try:
        serwer.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        serwer.zamknij()
        log("wektory: zatrzymana")
    return 0


def sprawdz(a) -> int:
    start = time.perf_counter()
    model = ModelE5(Path(a.model), a.watki)
    zaladowanie = time.perf_counter() - start
    teksty = [f"query: {t}" for t in (a.teksty or ["Gdzie leży kod strony?"])]
    start = time.perf_counter()
    wektory = OsadzanieLokalne(model, model.id, model.wymiar).osadz(teksty)
    ms = (time.perf_counter() - start) * 1000
    normy = [round(sum(x * x for x in v) ** 0.5, 4) for v in wektory]
    print(json.dumps({"model": model.id, "wymiar": model.wymiar, "zaladowanie_s": round(zaladowanie, 2),
                      "ms": round(ms, 1), "normy": normy}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    _lib().utf8_wyjscie()
    ap = argparse.ArgumentParser(description="Usługa wektorów skarbca wiedzy (multilingual-e5-small, docs/WIEDZA.md §7)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serwuj", help="usługa HTTP na 127.0.0.1 z tokenem w <stan>/wektory.json")
    s.add_argument("--model", required=True, help="katalog z model_quantized.onnx i tokenizer.json")
    s.add_argument("--stan", required=True, help="katalog stanu skarbca (<dane>/jarvo/state)")
    s.add_argument("--skarbiec", help="skarbiec: po starcie nadrób brakujące wektory")
    s.add_argument("--watki", type=int, default=WATKI)
    s.add_argument("--port", type=int, default=0, help="0 = wolny port wybrany przez system")
    p = sub.add_parser("sprawdz", help="załaduj model, osadź zdania, pokaż wymiar i czas")
    p.add_argument("--model", required=True)
    p.add_argument("--watki", type=int, default=WATKI)
    p.add_argument("teksty", nargs="*")
    a = ap.parse_args(argv)
    return serwuj(a) if a.cmd == "serwuj" else sprawdz(a)


if __name__ == "__main__":
    raise SystemExit(main())
