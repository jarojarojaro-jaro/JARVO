"""Wtyczka jarvo-przegladarka (komputer/przegladarka_plugin): wyniki browser_* bez rad o Browserbase, blokada
antybotowa rozpoznana po treści, widok strony po kliknięciu."""
from __future__ import annotations

import json
import sys
import types

from conftest import load_script

W = load_script("komputer/przegladarka_plugin/__init__.py", "jarvo_przegladarka_plugin")


def test_nawigacja_bez_rad_o_browserbase():
    wynik = {"success": True, "url": "https://example.com/", "title": "Example Domain", "snapshot": "x" * 500,
             "stealth_warning": "Consider upgrading Browserbase plan", "stealth_features": ["local"]}
    nowy = json.loads(W.przerob("browser_navigate", {}, json.dumps(wynik)))
    assert "stealth_warning" not in nowy and "stealth_features" not in nowy and "bot_detection_warning" not in nowy
    assert W.przerob("browser_navigate", {}, json.dumps({"success": True, "title": "A", "snapshot": "y" * 500})) is None


def test_blokada_po_tresci_i_pustej_stronie():
    cf = {"success": True, "url": "https://www.scrapingcourse.com/x", "title": "Cierpliwości...",
          "snapshot": "adres: https://www.scrapingcourse.com/x\nPrzeprowadzanie weryfikacji zabezpieczeń"}
    assert "telefonie floty" in json.loads(W.przerob("browser_navigate", {}, json.dumps(cf)))["bot_detection_warning"]
    g2 = {"success": True, "url": "https://www.g2.com/", "title": "g2.com", "snapshot": "adres: https://www.g2.com/\n"}
    assert "pusta strona" in json.loads(W.przerob("browser_navigate", {}, json.dumps(g2)))["bot_detection_warning"]
    artykul = {"success": True, "url": "https://blog.pl/", "title": "Blog", "snapshot": "Cloudflare i CAPTCHA " * 300}
    assert W.przerob("browser_navigate", {}, json.dumps(artykul)) is None


def test_klik_dostaje_widok_po_ustaleniu(monkeypatch):
    narzedzie = types.SimpleNamespace(browser_snapshot=lambda task_id=None: json.dumps(
        {"success": True, "snapshot": f"adres: https://a.pl/2\n[e1] link \"Dalej\" ({task_id})", "element_count": 1}))
    monkeypatch.setitem(sys.modules, "tools", types.SimpleNamespace(browser_tool=narzedzie))
    monkeypatch.setitem(sys.modules, "tools.browser_tool", narzedzie)
    nowy = json.loads(W.przerob("browser_click", {"ref": "@e3"}, json.dumps({"success": True, "clicked": "@e3"}),
                                task_id="t1"))
    assert nowy["stan_po"] == 'adres: https://a.pl/2\n[e1] link "Dalej" (t1)' and nowy["element_count"] == 1
    assert W.przerob("browser_click", {}, json.dumps({"success": False, "error": "x"}), task_id="t1") is None
    assert W.przerob("browser_type", {}, json.dumps({"success": True}), task_id="t1") is None
