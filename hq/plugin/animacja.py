"""Animacja HTML w HQ: podgląd na żywo (przewijanie przez __seek), parametry ze schematu i stan pomiaru.

Kontrakt (profiles/jarvo-wideo/skills/wideo/rodzaje-filmu/references/kontrakt-html.md, reguły 6–7): strona ma
`window.__seek(t)` i `window.__ready`; parametry do strojenia leżą w `parametry.json` obok strony, a strona czyta je
przy starcie i trzyma w `window.__params` (HQ podmienia wartości na żywo i woła `__seek`). Ten moduł nie zna FastAPI:
plugin_api.py woła jego czyste funkcje (testy: tests/test_animacja.py).
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

PARAMETRY = "parametry.json"
TYPY = {"liczba", "kolor", "tekst", "przelacznik", "wybor", "krzywa"}
MAKS_POL = 40
MAKS_TEKST = 400
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class ParamError(ValueError):
    pass


def to_animacja(p: Path) -> bool:
    """Strona HTML z naszym kontraktem: parametry.json obok albo `__seek` w kodzie strony."""
    if p.suffix.lower() not in (".html", ".htm") or not p.is_file():
        return False
    if (p.parent / PARAMETRY).is_file():
        return True
    try:
        with p.open("rb") as f:
            return b"__seek" in f.read(512_000)
    except OSError:
        return False


def _pole(p: Any, i: int) -> dict:
    if not isinstance(p, dict):
        raise ParamError(f"pole {i}: musi być obiektem")
    klucz, typ = str(p.get("klucz") or ""), p.get("typ")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,40}", klucz):
        raise ParamError(f"pole {i}: klucz {klucz!r} (litery, cyfry, _; jak zmienna w JS)")
    if typ not in TYPY:
        raise ParamError(f"pole {klucz}: typ {typ!r} ({' | '.join(sorted(TYPY))})")
    out = {"klucz": klucz, "typ": typ, "etykieta": str(p.get("etykieta") or klucz)[:60]}
    if p.get("opis"):
        out["opis"] = str(p["opis"])[:160]
    if typ == "liczba":
        lo, hi = float(p.get("min", 0)), float(p.get("max", 1))
        if not lo < hi:
            raise ParamError(f"pole {klucz}: min < max")
        out.update(min=lo, max=hi, krok=float(p.get("krok") or (hi - lo) / 100))
    if typ == "wybor":
        opcje = [str(o)[:60] for o in (p.get("opcje") or [])][:20]
        if len(opcje) < 2:
            raise ParamError(f"pole {klucz}: wybór potrzebuje co najmniej 2 opcji")
        out["opcje"] = opcje
    out["wartosc"] = wartosc(out, p.get("wartosc"))
    return out


def wartosc(pole: dict, v: Any) -> Any:
    """Wartość zgodna z typem pola (albo ParamError z czytelnym powodem)."""
    k, typ = pole["klucz"], pole["typ"]
    if typ == "liczba":
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ParamError(f"{k}: liczba")
        if not pole["min"] <= v <= pole["max"]:
            raise ParamError(f"{k}: {v} poza zakresem {pole['min']:g}–{pole['max']:g}")
        return v
    if typ == "kolor":
        if not isinstance(v, str) or not HEX.match(v):
            raise ParamError(f"{k}: kolor #RRGGBB")
        return v.upper()
    if typ == "tekst":
        if not isinstance(v, str) or len(v) > MAKS_TEKST:
            raise ParamError(f"{k}: tekst do {MAKS_TEKST} znaków")
        return v
    if typ == "przelacznik":
        if not isinstance(v, bool):
            raise ParamError(f"{k}: tak/nie")
        return v
    if typ == "wybor":
        if v not in pole["opcje"]:
            raise ParamError(f"{k}: jedna z opcji {', '.join(pole['opcje'])}")
        return v
    # krzywa: cubic-bezier(x1, y1, x2, y2), x w 0–1, y z zapasem na „sprężystość”
    if not (isinstance(v, list) and len(v) == 4 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)):
        raise ParamError(f"{k}: krzywa [x1, y1, x2, y2]")
    if not (0 <= v[0] <= 1 and 0 <= v[2] <= 1 and all(-1 <= y <= 2 for y in (v[1], v[3]))):
        raise ParamError(f"{k}: x1, x2 w 0–1, y1, y2 w −1–2")
    return [round(float(x), 4) for x in v]


def schemat(data: Any) -> list[dict]:
    if not isinstance(data, dict) or not isinstance(data.get("pola"), list):
        raise ParamError("parametry.json: obiekt z listą `pola`")
    if len(data["pola"]) > MAKS_POL:
        raise ParamError(f"parametry.json: najwyżej {MAKS_POL} pól")
    pola = [_pole(p, i) for i, p in enumerate(data["pola"])]
    if len({p["klucz"] for p in pola}) != len(pola):
        raise ParamError("parametry.json: klucze pól muszą być różne")
    return pola


def wczytaj(anim: Path) -> dict | None:
    """{pola, blad?} z parametry.json obok strony; None = animacja bez parametrów."""
    f = anim.parent / PARAMETRY
    if not f.is_file():
        return None
    try:
        return {"pola": schemat(json.loads(f.read_text(encoding="utf-8")))}
    except (OSError, ValueError) as e:
        return {"pola": [], "blad": str(e)}


def zapisz(anim: Path, wartosci: dict) -> list[dict]:
    """Nowe wartości pól (tylko istniejące klucze, typy sprawdzone) → parametry.json, zapis atomowy."""
    f = anim.parent / PARAMETRY
    data = json.loads(f.read_text(encoding="utf-8"))
    pola = schemat(data)
    if not isinstance(wartosci, dict) or not wartosci:
        raise ParamError("brak wartości do zapisania")
    po_kluczu = {p["klucz"]: p for p in pola}
    nieznane = sorted(set(wartosci) - set(po_kluczu))
    if nieznane:
        raise ParamError(f"nieznane pola: {', '.join(nieznane)}")
    nowe = {k: wartosc(po_kluczu[k], v) for k, v in wartosci.items()}
    for surowe in data["pola"]:
        if surowe.get("klucz") in nowe:
            surowe["wartosc"] = nowe[surowe["klucz"]]
    tmp = f.with_name(f".{f.name}.part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(f)
    return schemat(data)


def _pomiar_mod():
    here = Path(__file__).resolve().parent
    for cand in (here / "pomiar.py", here.parents[1] / "profiles" / "jarvo-wideo" / "scripts" / "pomiar.py"):
        if cand.is_file():
            if "jarvo_hq_pomiar" not in sys.modules:
                spec = importlib.util.spec_from_file_location("jarvo_hq_pomiar", cand)
                mod = importlib.util.module_from_spec(spec)
                sys.modules["jarvo_hq_pomiar"] = mod
                spec.loader.exec_module(mod)
            return sys.modules["jarvo_hq_pomiar"]
    return None


def pomiar(anim: Path) -> dict | None:
    """Stan raportu `pomiar.json` obok strony: werdykt, aktualność (odcisk plików) i ustalenia do listy w HQ."""
    f = anim.parent / "pomiar.json"
    if not f.is_file():
        return None
    try:
        r = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"blad": "pomiar.json nieczytelny"}
    pm = _pomiar_mod()
    powody = pm.aktualnosc(anim, r) if pm else ["brak modułu pomiaru w HQ"]
    ust = sorted(r.get("ustalenia") or [], key=lambda u: (bool(u.get("wyjatek")), u.get("waga") != "blad", u.get("od", 0)))
    return {"kiedy": r.get("kiedy"), "werdykt": r.get("werdykt"), "pokrycie": r.get("pokrycie"), "powody": powody,
            "aktualny": not powody, "ustalenia": [{k: u.get(k) for k in ("kod", "waga", "opis", "poprawka", "od", "do", "wyjatek")}
                                                  for u in ust[:40]]}


# Mostek podglądu: wstrzykiwany przez serwer :9120 tylko z ?jarvo-podglad=1. Strona ma nieprzezroczyste pochodzenie
# (CSP sandbox), więc HQ rozmawia z nią przez postMessage: seek, parametry, odpowiedź z czasem i rozmiarem kadru.
MOST_JS = r"""(() => {
  const send = (m) => parent.postMessage({ jarvo: "anim", ...m }, "*");
  const ready = () => new Promise((ok) => { const k = () => (window.__ready === true ? ok() : setTimeout(k, 40)); k(); });
  addEventListener("error", (e) => send({ typ: "blad", tekst: String(e.message || e) }));
  addEventListener("message", async (e) => {
    const d = e.data || {};
    if (e.source !== parent || d.jarvo !== "hq") return;
    await ready();
    try {
      if (d.typ === "params" && d.wartosci && typeof d.wartosci === "object") {
        if (typeof window.__setParams === "function") window.__setParams(d.wartosci);
        else if (window.__params && typeof window.__params === "object") Object.assign(window.__params, d.wartosci);
      }
      if (typeof d.t === "number" && typeof window.__seek === "function") {
        const r = window.__seek(d.t);
        if (r && typeof r.then === "function" && r instanceof Promise) await r;
      }
      send({ typ: "klatka", id: d.id, t: d.t });
    } catch (err) { send({ typ: "blad", id: d.id, tekst: String((err && err.message) || err) }); }
  });
  ready().then(() => send({ typ: "gotowe", W: window.__W || innerWidth, H: window.__H || innerHeight,
    DUR: window.__DUR || null, parametry: !!(window.__params || window.__setParams) }));
})();
"""


def wstrzyknij_most(html: bytes) -> bytes:
    tag = b'<script src="/_jarvo/most.js"></script>'
    low = html.lower()
    i = low.rfind(b"</body>")
    return html[:i] + tag + html[i:] if i >= 0 else html + tag
