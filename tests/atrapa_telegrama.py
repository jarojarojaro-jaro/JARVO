"""Atrapa Bot API Telegrama (`sendMessage`) na 127.0.0.1 dla lustra panelu (tests/test_lustro.py, test_centrum_silnik.py).

`JARVO_TELEGRAM_API=atrapa.adres` kieruje tam lustro.wyslij. `wyslane` = lista {token, chat_id, message_thread_id, text};
`awaria = n` odpowiada błędem API na n kolejnych wysyłek (próby lustra).
"""
from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class AtrapaTelegrama:
    def __init__(self):
        self.wyslane: list[dict] = []
        self.awaria = 0
        self._lock = threading.Lock()
        atrapa = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def do_POST(self):
                m = re.fullmatch(r"/bot([^/]+)/sendMessage", self.path)
                dane = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                with atrapa._lock:
                    if not m:
                        kod, odp = 404, {"ok": False, "description": "Not Found"}
                    elif atrapa.awaria > 0:
                        atrapa.awaria -= 1
                        kod, odp = 400, {"ok": False, "description": f"Bad Request: bot{m.group(1)} chat not found"}
                    else:
                        atrapa.wyslane.append({"token": m.group(1), **dane})
                        kod, odp = 200, {"ok": True, "result": {"message_id": len(atrapa.wyslane)}}
                body = json.dumps(odp).encode()
                self.send_response(kod)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.serwer = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.adres = f"http://127.0.0.1:{self.serwer.server_address[1]}"
        self._watek = threading.Thread(target=self.serwer.serve_forever, daemon=True)
        self._watek.start()

    def teksty(self) -> list[str]:
        with self._lock:
            return [w["text"] for w in self.wyslane]

    def zamknij(self) -> None:
        self.serwer.shutdown()
        self.serwer.server_close()
